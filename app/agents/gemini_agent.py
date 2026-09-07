import json
import asyncio
import logging
from typing import Dict, Any
from google import genai
from google.genai import types
from app.config import settings
from app.agents.base import ILLMAgent
from app.agents.mcp_client import MCPClientHelper
from app.agents.validator import validate_user_intent
from app.engine.chart_selector import determine_chart_type
from app.engine.insight_gen import generate_insight_llm

logger = logging.getLogger("analytics_chatbot")

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
                        description="Get order trends over time (monthly) or by state. Use this for monthly revenue, volume, or delivery performance.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "metric": types.Schema(type=types.Type.STRING, description="Must be 'revenue', 'orders', or 'delivery'"),
                                "start_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "end_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "group_by": types.Schema(type=types.Type.STRING, description="'month' or 'state' (optional, default 'month')")
                            },
                            required=["metric"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_product_category_performance",
                        description="Get product category performance (revenue, order count, average review score).",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "category_name_english": types.Schema(type=types.Type.STRING, description="Filter by specific category, MUST use english translation (e.g. 'electronics')."),
                                "limit": types.Schema(type=types.Type.INTEGER, description="Top N results (default 10)"),
                                "sort_by": types.Schema(type=types.Type.STRING, description="Must be 'revenue', 'orders', or 'review_score'")
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
                        description="Get customer reviews or review score distribution (1 to 5 stars).",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "category_name_english": types.Schema(type=types.Type.STRING, description="filter by category (optional)"),
                                "group_by": types.Schema(type=types.Type.STRING, description="'month' or 'state' or null for score distribution"),
                                "start_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "end_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)")
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
                    ),
                    types.FunctionDeclaration(
                        name="get_seller_delivery_review_correlation",
                        description="Get correlation between delivery time and average review score by seller.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "start_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)"),
                                "end_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD (optional)")
                            }
                        )
                    )
                ]
            )
        ]

    async def query(self, user_text: str) -> Dict[str, Any]:
        # Pre-validate intent before calling any MCP tool or LLM tool selection
        is_valid, intent, confidence = validate_user_intent(user_text)

        logger.info(f"User query: {user_text}")
        logger.info(f"Detected intent: {intent}")
        logger.info(f"Confidence: {confidence:.2f}")

        if not is_valid or intent == "unsupported":
            logger.info("MCP tool: none")
            logger.info("Chart: none")
            return {
                "error": f"I couldn't identify a supported analytics request from '{user_text}'. Please ask a question about revenue, orders, categories, payments, reviews, sellers, or delivery performance.",
                "type": "unsupported_intent"
            }

        system_instruction = """
        You are an expert e-commerce data analysis agent.
        Choose the right tool to answer the user's analytical question.
        
        CRITICAL RULES:
        - ONLY call a tool if the question asks for supported e-commerce analytics.
        - "last year" means start_date: 2017-01-01, end_date: 2017-12-31.
        - "2017" means start_date: 2017-01-01, end_date: 2017-12-31.
        - "first half of 2017" means start_date: 2017-01-01, end_date: 2017-06-30.
        - "São Paulo" means state: SP.
        - "top 10" means limit: 10, sort: desc.
        - "worst rated" means sort: asc by review score.
        - If user asks for category like "electronics", pass "electronics" to category_name_english.
        - If no date range is specified, leave start_date and end_date blank.
        - NEVER call a tool if the query does not ask a real analytics question.
        """
        
        try:
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
            logger.info("MCP tool: none")
            logger.info("Chart: none")
            return {
                "error": f"I couldn't identify a supported analytics request from '{user_text}'. Please ask a question about revenue, orders, categories, payments, reviews, sellers, or delivery performance.",
                "type": "unsupported_intent"
            }
            
        function_call = response.function_calls[0]
        tool_name = function_call.name
        arguments = function_call.args if function_call.args else {}
        
        logger.info(f"MCP tool: {tool_name}")
        logger.info(f"Parameters: {arguments}")

        assumed_dataset = ""
        if "start_date" not in arguments and tool_name in ["get_order_trends", "get_payment_breakdown"]:
            assumed_dataset = "Assuming full dataset (2016-01-01 to 2018-12-31) because no date range was specified."

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
        logger.info(f"Chart: {chart_config.get('type')}")
        
        # Generate Insight
        insight = generate_insight_llm(raw_data, user_text)
        if assumed_dataset and not insight.endswith(assumed_dataset):
            insight += " " + assumed_dataset

        return {
            "chart_config": chart_config,
            "chart_type_justification": chart_type_justification,
            "insight": insight,
            "raw_data": raw_data,
            "tool_calls": [{"tool": tool_name, "arguments": arguments}],
            "assumed_dataset": assumed_dataset
        }
