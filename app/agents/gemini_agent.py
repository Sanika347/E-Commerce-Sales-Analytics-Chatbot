import json
import asyncio
from typing import Dict, Any
from google import genai
from google.genai import types
from app.config import settings
from app.agents.base import ILLMAgent
from app.agents.mcp_client import MCPClientHelper
from app.engine.chart_selector import determine_chart_type
from app.engine.insight_gen import generate_insight_llm

class GeminiAgent(ILLMAgent):
    def __init__(self):
        self.mcp = MCPClientHelper()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        
        # Define the tools available for the LLM based on our MCP tools
        self.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="get_order_trends",
                        description="Get order trends over time (monthly). Use this for monthly revenue, volume, or delivery performance.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "metric": types.Schema(type=types.Type.STRING, description="Must be 'revenue', 'volume', or 'delivery'"),
                                "start_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "end_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                            },
                            required=["metric"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_product_category_performance",
                        description="Get product category performance (revenue, average review score).",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "category_name_english": types.Schema(type=types.Type.STRING, description="Filter by specific category, MUST use english translation (e.g. 'electronics')."),
                                "limit": types.Schema(type=types.Type.INTEGER, description="Top N results (default 10)"),
                                "sort_by": types.Schema(type=types.Type.STRING, description="Must be 'revenue' or 'review_score'")
                            },
                            required=["sort_by"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_seller_performance",
                        description="Get top sellers by revenue.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "state": types.Schema(type=types.Type.STRING, description="filter by seller state code (e.g. 'SP')"),
                                "limit": types.Schema(type=types.Type.INTEGER, description="Top N results (default 10)"),
                                "sort_order": types.Schema(type=types.Type.STRING, description="Must be 'desc' (top sellers) or 'asc' (worst sellers)")
                            },
                            required=["sort_order"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_customer_reviews",
                        description="Get review score distribution (1 to 5 stars).",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "category_name_english": types.Schema(type=types.Type.STRING, description="filter by category (optional)")
                            }
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_payment_breakdown",
                        description="Get share of different payment types.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "start_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "end_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "payment_types": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(type=types.Type.STRING),
                                    description="Filter by specific payment types, e.g. ['credit_card', 'boleto'] (optional)"
                                )
                            }
                        )
                    )
                ]
            )
        ]

    async def query(self, user_text: str) -> Dict[str, Any]:
        system_instruction = """
        You are a data analysis agent. Choose the right tool to answer the user's question.
        Guidelines:
        - "last year" means from: 2017-01-01, to: 2017-12-31.
        - "first half of 2017" means from: 2017-01-01, to: 2017-06-30.
        - "São Paulo" means state: SP.
        - "top 10" means limit: 10, sort: desc.
        - "worst rated" means sort: asc by average review score.
        - If the user asks for a category like "electronics", pass "electronics" to category_name_english.
        - If no date range is specified, leave start_date and end_date blank.
        """
        
        try:
            # Add timeout of 10s to the LLM call using asyncio.wait_for
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model='gemini-1.5-pro',
                    contents=user_text,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=self.tools,
                        temperature=0
                    )
                ),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            return {"error": "LLM agent timed out.", "type": "timeout"}
        except Exception as e:
            return {"error": f"LLM error: {str(e)}", "type": "llm_error"}

        # Extract tool call
        if not response.function_calls:
            return {"error": "Query outside dataset scope.", "type": "guardrail"}
            
        function_call = response.function_calls[0]
        tool_name = function_call.name
        arguments = function_call.args if function_call.args else {}
        
        assumed_dataset = ""
        if "start_date" not in arguments and tool_name in ["get_order_trends", "get_payment_breakdown"]:
            assumed_dataset = "Assuming full dataset as no date range was specified."

        # Call MCP tool
        raw_result_str = await self.mcp.call_tool(tool_name, arguments)
        try:
            raw_data = json.loads(raw_result_str)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON from tool", "raw_data": raw_result_str}
            
        if isinstance(raw_data, dict) and "error" in raw_data:
            return {"error": raw_data["error"], "tool": tool_name}
            
        if not raw_data:
            return {"error": "No data found for your filters.", "type": "empty"}

        # Determine Chart Type
        chart_config, chart_type_justification = determine_chart_type(raw_data, tool_name, user_text)
        
        # Generate Insight
        insight = generate_insight_llm(raw_data, user_text)
        if assumed_dataset:
            insight += " " + assumed_dataset

        return {
            "chart_config": chart_config,
            "chart_type_justification": chart_type_justification,
            "insight": insight,
            "raw_data": raw_data,
            "tool_calls": [{"tool": tool_name, "arguments": arguments}],
            "assumed_dataset": assumed_dataset
        }
