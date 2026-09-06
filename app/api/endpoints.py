from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import json
import uuid
from typing import Dict, Any, List

from app.config import settings
from app.agents.gemini_agent import GeminiAgent
from app.agents.fallback_agent import FallbackAgent
from app.agents.mcp_client import MCPClientHelper
from app.engine.chart_selector import determine_chart_type

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

class PinRequest(BaseModel):
    user_query: str
    chart_config: Dict[str, Any]
    raw_data: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    insight: str

def get_agent():
    if settings.agent_mode == "llm":
        return GeminiAgent()
    return FallbackAgent()

def get_dashboard_db():
    conn = sqlite3.connect(settings.dashboard_db_path)
    conn.row_factory = sqlite3.Row
    return conn

@router.post("/query")
async def query_endpoint(req: QueryRequest):
    agent = get_agent()
    result = await agent.query(req.question)
    
    if "error" in result:
        # Return HTTP 200 with error details as requested by standard JSON error handling
        return {"error": result["error"], "type": result.get("type", "general")}
        
    return result

@router.get("/dashboard")
def get_dashboard():
    with get_dashboard_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dashboard ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "user_query": row["user_query"],
                "chart_config": json.loads(row["chart_config"]),
                "raw_data": json.loads(row["raw_data"]),
                "tool_calls": json.loads(row["tool_calls"]),
                "insight": row["insight"],
                "created_at": row["created_at"]
            })
        return result

@router.post("/dashboard/pin")
def pin_chart(req: PinRequest):
    new_id = str(uuid.uuid4())
    with get_dashboard_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dashboard (id, user_query, chart_config, raw_data, tool_calls, insight)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            new_id, 
            req.user_query, 
            json.dumps(req.chart_config), 
            json.dumps(req.raw_data), 
            json.dumps(req.tool_calls), 
            req.insight
        ))
        conn.commit()
    return {"status": "success", "id": new_id}

@router.delete("/dashboard/{item_id}")
def delete_pin(item_id: str):
    with get_dashboard_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dashboard WHERE id = ?", (item_id,))
        conn.commit()
    return {"status": "success"}

@router.post("/dashboard/{item_id}/refresh")
async def refresh_chart(item_id: str):
    # Retrieve existing data
    with get_dashboard_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dashboard WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
        
    tool_calls = json.loads(row["tool_calls"])
    old_raw_data = json.loads(row["raw_data"])
    
    # Re-run tools
    if not tool_calls:
        return {"changed": False, "message": "No tool calls available to refresh"}
        
    tool_name = tool_calls[0]["tool"]
    arguments = tool_calls[0]["arguments"]
    
    mcp = MCPClientHelper()
    new_result_str = await mcp.call_tool(tool_name, arguments)
    
    try:
        new_raw_data = json.loads(new_result_str)
    except Exception as e:
        return {"error": "Failed to parse refreshed data"}
        
    if isinstance(new_raw_data, dict) and "error" in new_raw_data:
        return {"error": new_raw_data["error"]}
        
    # Calculate difference
    # Let's take the first numerical column of the first row to compare
    significant_change = False
    message = "No significant change."
    
    if len(old_raw_data) > 0 and len(new_raw_data) > 0:
        first_row_old = old_raw_data[0]
        first_row_new = new_raw_data[0]
        
        # Find first numeric key
        numeric_key = None
        for key, val in first_row_old.items():
            if isinstance(val, (int, float)):
                numeric_key = key
                break
                
        if numeric_key and numeric_key in first_row_new:
            old_val = first_row_old[numeric_key]
            new_val = first_row_new[numeric_key]
            
            if old_val != 0:
                percent_change = abs((new_val - old_val) / old_val) * 100
                if percent_change > 5.0:
                    significant_change = True
                    message = f"Significant change detected: {numeric_key} changed by {percent_change:.1f}%."
    elif len(old_raw_data) != len(new_raw_data):
        significant_change = True
        message = "Number of rows changed significantly."

    user_query = row["user_query"]
    # Generate new chart config
    new_chart_config = determine_chart_type(new_raw_data, tool_name, user_query)
    
    # Update DB
    with get_dashboard_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dashboard 
            SET raw_data = ?, chart_config = ?
            WHERE id = ?
        """, (json.dumps(new_raw_data), json.dumps(new_chart_config), item_id))
        conn.commit()
        
    return {
        "changed": significant_change, 
        "message": message,
        "new_chart": new_chart_config
    }
