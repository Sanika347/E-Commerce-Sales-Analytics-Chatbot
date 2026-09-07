import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base import ILLMAgent
from app.agents.mcp_client import MCPClientHelper
from app.engine.insight_gen import generate_insight_fallback
from app.engine.chart_selector import determine_chart_type


class FallbackAgent(ILLMAgent):
    """
    Deterministic fallback agent for the AI Data Analyst.

    Pipeline:

        User Query
            ↓
        Parameter Extraction
            ↓
        Intent Detection
            ↓
        MCP Tool Selection
            ↓
        MCP Tool Execution
            ↓
        Data Shape Detection
            ↓
        Chart Selection
            ↓
        Insight Generation
            ↓
        Structured Response
    """

    # ================================================================
    # MCP TOOLS
    # ================================================================

    ORDER_TRENDS_TOOL = "get_order_trends"
    CATEGORY_TOOL = "get_product_category_performance"
    SELLER_TOOL = "get_seller_performance"
    PAYMENT_TOOL = "get_payment_breakdown"
    REVIEW_TOOL = "get_customer_reviews"
    SELLER_CORRELATION_TOOL = "get_seller_delivery_review_correlation"

    SUPPORTED_TOOLS = {
        ORDER_TRENDS_TOOL,
        CATEGORY_TOOL,
        SELLER_TOOL,
        PAYMENT_TOOL,
        REVIEW_TOOL,
        SELLER_CORRELATION_TOOL,
    }

    # ================================================================
    # DATASET KNOWLEDGE
    # ================================================================

    DATASET_START_YEAR = 2016
    DATASET_END_YEAR = 2018

    CATEGORY_TRANSLATIONS = {
        "electronics": "electronics",
        "electronic": "electronics",
        "eletronicos": "electronics",
        "eletrônicos": "electronics",

        "computers": "computers",
        "computer": "computers",
        "computer accessories": "computers",

        "furniture": "furniture",

        "home appliances": "home_appliances",
        "home appliance": "home_appliances",
        "appliances": "home_appliances",

        "fashion": "fashion",
        "clothing": "fashion",

        "sports": "sports",
        "toys": "toys",
        "books": "books",
        "health": "health",
        "beauty": "beauty",
        "automotive": "automotive",
        "garden": "garden",
    }

    # ================================================================
    # STATE TRANSLATION
    # ================================================================

    STATE_CODES = {
        "sao paulo": "SP",
        "são paulo": "SP",
        "sp": "SP",

        "rio de janeiro": "RJ",
        "rj": "RJ",

        "minas gerais": "MG",
        "mg": "MG",

        "bahia": "BA",
        "ba": "BA",

        "parana": "PR",
        "paraná": "PR",
        "pr": "PR",

        "santa catarina": "SC",
        "sc": "SC",

        "rio grande do sul": "RS",
        "rs": "RS",

        "pernambuco": "PE",
        "pe": "PE",

        "ceara": "CE",
        "ceará": "CE",
        "ce": "CE",

        "goias": "GO",
        "goiás": "GO",
        "go": "GO",

        "amazonas": "AM",
        "am": "AM",

        "para": "PA",
        "pará": "PA",
        "pa": "PA",

        "espirito santo": "ES",
        "espírito santo": "ES",
        "es": "ES",
    }

    # ================================================================
    # CONSTRUCTOR
    # ================================================================

    def __init__(self):
        self.mcp = MCPClientHelper()

    # ================================================================
    # MAIN QUERY
    # ================================================================

    async def query(self, user_text: str) -> Dict[str, Any]:

        if not isinstance(user_text, str) or not user_text.strip():
            return self._error_response(
                "User query must be a non-empty string.",
                "invalid_input",
            )

        original_query = user_text.strip()
        query = self._normalize_query(original_query)

        # ------------------------------------------------------------
        # 1. Parameters
        # ------------------------------------------------------------

        parameters = self._extract_parameters(query)

        # ------------------------------------------------------------
        # 2. Intent
        # ------------------------------------------------------------

         intent = self._detect_intent(query)
        if not is_valid:
            intent = "unsupported"

        logger.info(f"User query: {original_query}")
        logger.info(f"Detected intent: {intent}")
        logger.info(f"Confidence: {confidence:.2f}")

        if intent == "unsupported":
            logger.info("MCP tool: none")
            logger.info("Chart: none")
            return self._error_response(
                f"I couldn't identify a supported analytics request from '{original_query}'. Please ask a question about revenue, orders, categories, payments, reviews, sellers, or delivery performance.",
                "unsupported_intent"
            )


        # ------------------------------------------------------------
        # 3. MCP requests
        # ------------------------------------------------------------

        tool_requests = self._build_tool_requests(
            intent=intent,
            parameters=parameters,
        )

        if not tool_requests:
            return self._error_response(
                "No MCP tool request could be created.",
                "no_tool_request",
            )

        # ------------------------------------------------------------
        # 4. Execute tools
        # ------------------------------------------------------------

        tool_calls_record = []
        datasets = []

        for tool_name, arguments in tool_requests:

            tool_calls_record.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                }
            )

            if tool_name not in self.SUPPORTED_TOOLS:
                return self._error_response(
                    f"Unsupported tool: {tool_name}",
                    "unsupported_tool",
                    tool=tool_name,
                    arguments=arguments,
                )

            try:
                raw_result = await self.mcp.call_tool(
                    tool_name,
                    arguments,
                )

            except Exception as exc:
                return self._error_response(
                    f"MCP tool execution failed: {str(exc)}",
                    "tool_execution_error",
                    tool=tool_name,
                    arguments=arguments,
                )

            # --------------------------------------------------------
            # Robust MCP response parsing
            # --------------------------------------------------------

            raw_data = self._parse_mcp_result(raw_result)

            if raw_data is None:
                return self._error_response(
                    "Invalid JSON returned by MCP tool.",
                    "invalid_tool_response",
                    tool=tool_name,
                    arguments=arguments,
                    raw_data=self._safe_repr(raw_result),
                )

            if isinstance(raw_data, dict) and raw_data.get("error"):
                return self._error_response(
                    str(raw_data["error"]),
                    "tool_error",
                    tool=tool_name,
                    arguments=arguments,
                    raw_data=raw_data,
                )

            if self._is_empty(raw_data):
                continue

            datasets.append(
                {
                    "tool": tool_name,
                    "data": raw_data,
                }
            )

        # ------------------------------------------------------------
        # 5. Merge data according to intent
        # ------------------------------------------------------------

        raw_data = self._merge_tool_results(
            datasets=datasets,
            intent=intent,
        )

        if not raw_data:
            return self._error_response(
                "No data was returned for the requested query.",
                "empty_result",
                raw_data=[],
            )

        # ------------------------------------------------------------
        # 6. Data shape
        # ------------------------------------------------------------

        primary_tool = (
            tool_requests[0][0]
            if tool_requests
            else ""
        )

        data_shape = self._detect_data_shape(
            data=raw_data,
            tool_name=primary_tool,
            query=query,
            parameters=parameters,
            intent=intent,
        )

        # ------------------------------------------------------------
        # 7. Chart selection
        # ------------------------------------------------------------

        chart_config_js, chart_justification = determine_chart_type(raw_data, primary_tool, query)
        chart_selection = {
            "chart_type": chart_config_js.get("type", "bar"),
            "chart_config": chart_config_js,
            "justification": chart_justification,
            "chart_options": []
        }

        # ------------------------------------------------------------
        # 8. Insight
        # ------------------------------------------------------------

        try:
            insight = generate_insight_fallback(
                raw_data,
                query,
            )

        except Exception as exc:
            insight = (
                "Data was retrieved successfully, but the insight "
                f"could not be generated: {str(exc)}"
            )

        # ------------------------------------------------------------
        # 9. Dataset assumption
        # ------------------------------------------------------------

        assumed_dataset = parameters.get(
            "assumed_dataset",
            "Assuming the full dataset because no date range "
            "was specified.",
        )

        if parameters.get("date_range_specified") is False:
            insight = f"{insight} {assumed_dataset}"

        # ------------------------------------------------------------
        # 10. Final response
        # ------------------------------------------------------------

        return {
            "success": True,
            "query": original_query,
            "normalized_query": query,
            "intent": intent,
            "parameters": parameters,
            "tool_calls": tool_calls_record,
            "data_shape": data_shape,

            "chart_config": chart_config_js,

            "chart_type": chart_selection.get(
                "chart_type"
            ),

            "chart_type_justification": chart_selection.get(
                "justification"
            ),

            "chart_options": chart_selection.get(
                "chart_options",
                [],
            ),

            "insight": insight,
            "raw_data": raw_data,
            "assumed_dataset": assumed_dataset,
        }

    # ================================================================
    # MCP RESULT PARSER
    # ================================================================

    @classmethod
    def _parse_mcp_result(
        cls,
        value: Any,
    ) -> Optional[Any]:

        # Already parsed
        if isinstance(value, (dict, list)):
            return value

        # Direct string JSON
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None

        # ------------------------------------------------------------
        # MCP CallToolResult-like object
        #
        # Example:
        # result.content = [
        #     TextContent(type="text", text='[...]')
        # ]
        # ------------------------------------------------------------

        content = getattr(value, "content", None)

        if content is not None:

            texts = []

            for item in content:

                if isinstance(item, str):
                    texts.append(item)
                    continue

                text = getattr(item, "text", None)

                if text is not None:
                    texts.append(str(text))

            if texts:

                combined = "\n".join(texts).strip()

                try:
                    return json.loads(combined)
                except json.JSONDecodeError:
                    pass

                # Some MCP wrappers return a JSON string
                # inside another object.
                for text in texts:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        continue

        # ------------------------------------------------------------
        # Dict-like MCP object
        # ------------------------------------------------------------

        if hasattr(value, "model_dump"):

            try:
                dumped = value.model_dump()
                parsed = cls._parse_mcp_result(dumped)

                if parsed is not None:
                    return parsed

            except Exception:
                pass

        # ------------------------------------------------------------
        # Object converted to dictionary
        # ------------------------------------------------------------

        if hasattr(value, "__dict__"):

            try:
                obj_dict = vars(value)

                if obj_dict:
                    parsed = cls._parse_mcp_result(obj_dict)

                    if parsed is not None:
                        return parsed

            except Exception:
                pass

        return None

    @staticmethod
    def _safe_repr(value: Any) -> str:

        try:
            return repr(value)
        except Exception:
            return "<unrepresentable MCP response>"

    # ================================================================
    # CHART.JS CONFIG
    # ================================================================

    def _build_chartjs_config(
        self,
        chart_selection: Dict[str, Any],
        raw_data: Any,
    ) -> Dict[str, Any]:

        abstract_config = chart_selection.get(
            "chart_config"
        )

        if not abstract_config:
            return {}

        rows = self._get_rows(raw_data)

        if not rows:
            return {}

        c_type = abstract_config.get("type")

        # ------------------------------------------------------------
        # DONUT
        # ------------------------------------------------------------

        if c_type == "donut":

            label_key = self._first_existing_key(
                rows,
                [
                    "payment_type",
                    "payment_method",
                    "category",
                    "label",
                ],
            )

            value_key = self._first_numeric_key(
                rows,
                exclude=[
                    "id",
                ],
            )

            if not label_key or not value_key:
                return {}

            return {
                "type": "doughnut",
                "data": {
                    "labels": [
                        row.get(label_key)
                        for row in rows
                    ],
                    "datasets": [
                        {
                            "label": value_key,
                            "data": [
                                row.get(value_key)
                                for row in rows
                            ],
                        }
                    ],
                },
            }

        # ------------------------------------------------------------
        # LINE
        # ------------------------------------------------------------

        if c_type == "line":

            x_key = self._first_existing_key(
                rows,
                [
                    "month",
                    "date",
                    "year",
                    "period",
                ],
            )

            numeric_keys = self._numeric_columns(
                rows
            )

            y_keys = [
                key
                for key in numeric_keys
                if key != x_key
            ]

            if not x_key or not y_keys:
                return {}

            y_key = y_keys[0]

            return {
                "type": "line",
                "data": {
                    "labels": [
                        row.get(x_key)
                        for row in rows
                    ],
                    "datasets": [
                        {
                            "label": y_key,
                            "data": [
                                row.get(y_key)
                                for row in rows
                            ],
                            "fill": False,
                        }
                    ],
                },
            }

        # ------------------------------------------------------------
        # DUAL AXIS LINE
        # ------------------------------------------------------------

        if c_type == "dual_axis_line":

            x_key = self._first_existing_key(
                rows,
                [
                    "month",
                    "date",
                    "year",
                    "period",
                ],
            )

            numeric_keys = self._numeric_columns(
                rows
            )

            numeric_keys = [
                key
                for key in numeric_keys
                if key != x_key
                and "id" not in key.lower()
            ]

            if not x_key or len(numeric_keys) < 2:
                return {}

            metric_1 = numeric_keys[0]
            metric_2 = numeric_keys[1]

            return {
                "type": "line",
                "data": {
                    "labels": [
                        row.get(x_key)
                        for row in rows
                    ],
                    "datasets": [
                        {
                            "label": metric_1,
                            "data": [
                                row.get(metric_1)
                                for row in rows
                            ],
                            "yAxisID": "y",
                            "fill": False,
                        },
                        {
                            "label": metric_2,
                            "data": [
                                row.get(metric_2)
                                for row in rows
                            ],
                            "yAxisID": "y1",
                            "fill": False,
                        },
                    ],
                },
                "options": {
                    "responsive": True,
                    "scales": {
                        "y": {
                            "type": "linear",
                            "position": "left",
                            "title": {
                                "display": True,
                                "text": metric_1,
                            },
                        },
                        "y1": {
                            "type": "linear",
                            "position": "right",
                            "title": {
                                "display": True,
                                "text": metric_2,
                            },
                        },
                    },
                },
            }

        # ------------------------------------------------------------
        # SCATTER
        # ------------------------------------------------------------

        if c_type == "scatter":

            x_key = abstract_config.get(
                "x_axis"
            )

            y_key = abstract_config.get(
                "y_axis"
            )

            # If exact fields aren't present, detect numeric fields.
            if not x_key or x_key not in rows[0]:

                numeric_keys = self._numeric_columns(
                    rows
                )

                numeric_keys = [
                    key
                    for key in numeric_keys
                    if "id" not in key.lower()
                ]

                if len(numeric_keys) >= 2:
                    x_key = numeric_keys[0]
                    y_key = numeric_keys[1]

            if (
                not x_key
                or not y_key
                or x_key not in rows[0]
                or y_key not in rows[0]
            ):
                return {}

            points = []

            for row in rows:

                x = row.get(x_key)
                y = row.get(y_key)

                if x is None or y is None:
                    continue

                try:
                    points.append(
                        {
                            "x": float(x),
                            "y": float(y),
                        }
                    )
                except (TypeError, ValueError):
                    continue

            return {
                "type": "scatter",
                "data": {
                    "datasets": [
                        {
                            "label": (
                                f"{y_key} vs {x_key}"
                            ),
                            "data": points,
                        }
                    ],
                },
                "options": {
                    "responsive": True,
                    "scales": {
                        "x": {
                            "title": {
                                "display": True,
                                "text": x_key,
                            }
                        },
                        "y": {
                            "title": {
                                "display": True,
                                "text": y_key,
                            }
                        },
                    },
                },
            }

        # ------------------------------------------------------------
        # HORIZONTAL BAR
        # ------------------------------------------------------------

        if c_type == "horizontal_bar":

            label_key = self._first_label_key(
                rows
            )

            value_key = self._first_numeric_key(
                rows
            )

            if not label_key or not value_key:
                return {}

            return {
                "type": "bar",
                "data": {
                    "labels": [
                        row.get(label_key)
                        for row in rows
                    ],
                    "datasets": [
                        {
                            "label": value_key,
                            "data": [
                                row.get(value_key)
                                for row in rows
                            ],
                        }
                    ],
                },
                "options": {
                    "indexAxis": "y",
                },
            }

        # ------------------------------------------------------------
        # VERTICAL BAR
        # ------------------------------------------------------------

        if c_type == "vertical_bar":

            # If the chart config specifies exact keys to display, use them.
            explicit_value_key = abstract_config.get("value_key")
            explicit_label_key = abstract_config.get("label_key")

            if explicit_value_key and explicit_label_key:
                return {
                    "type": "bar",
                    "data": {
                        "labels": [
                            row.get(explicit_label_key)
                            for row in rows
                        ],
                        "datasets": [
                            {
                                "label": explicit_value_key,
                                "data": [
                                    row.get(explicit_value_key)
                                    for row in rows
                                ],
                            }
                        ],
                    },
                }

            # For two-metric state comparison,
            # create two datasets.
            numeric_keys = self._numeric_columns(
                rows
            )

            label_key = self._first_label_key(
                rows
            )

            LABEL_MAP = {
                "revenue": "Revenue (BRL)",
                "total_revenue": "Revenue (BRL)",
                "average_review_score": "Average Review Score (Stars)",
                "avg_review_score": "Average Review Score (Stars)",
                "review_score": "Review Score (Stars)",
                "delivery_delay": "Average Delivery Delay (Days)",
                "orders": "Number of Orders",
                "order_volume": "Number of Orders",
                "count": "Count",
                "payment_type": "Payment Method",
                "avg_freight": "Average Freight (BRL)"
            }

            def clean_label(k: str) -> str:
                return LABEL_MAP.get(k, k.replace("_", " ").title())

            if (
                label_key
                and len(numeric_keys) >= 2
            ):
                metric_1 = numeric_keys[0]
                metric_2 = numeric_keys[1]

                return {
                    "type": "bar",
                    "data": {
                        "labels": [
                            row.get(label_key)
                            for row in rows
                        ],
                        "datasets": [
                            {
                                "label": clean_label(metric_1),
                                "data": [
                                    row.get(metric_1)
                                    for row in rows
                                ],
                                "yAxisID": "y",
                                "backgroundColor": "rgba(54, 162, 235, 0.7)",
                            },
                            {
                                "label": clean_label(metric_2),
                                "data": [
                                    row.get(metric_2)
                                    for row in rows
                                ],
                                "yAxisID": "y1",
                                "backgroundColor": "rgba(255, 99, 132, 0.7)",
                            },
                        ],
                    },
                    "options": {
                        "responsive": True,
                        "scales": {
                            "y": {
                                "type": "linear",
                                "position": "left",
                                "title": {
                                    "display": True,
                                    "text": clean_label(metric_1),
                                },
                            },
                            "y1": {
                                "type": "linear",
                                "position": "right",
                                "title": {
                                    "display": True,
                                    "text": clean_label(metric_2),
                                },
                                "grid": {
                                    "drawOnChartArea": False,
                                },
                            },
                        },
                    },
                }

            value_key = (
                numeric_keys[0]
                if numeric_keys
                else None
            )

            if not label_key or not value_key:
                return {}

            return {
                "type": "bar",
                "data": {
                    "labels": [
                        row.get(label_key)
                        for row in rows
                    ],
                    "datasets": [
                        {
                            "label": value_key,
                            "data": [
                                row.get(value_key)
                                for row in rows
                            ],
                        }
                    ],
                },
            }

        # ------------------------------------------------------------
        # SCORE DISTRIBUTION
        # ------------------------------------------------------------

        if c_type == "stacked_horizontal_bar":

            score_key = self._first_existing_key(
                rows,
                [
                    "review_score",
                    "score",
                    "rating",
                    "stars",
                ],
            )

            count_key = self._first_existing_key(
                rows,
                [
                    "count",
                    "review_count",
                    "frequency",
                ],
            )

            if score_key and count_key:

                return {
                    "type": "bar",
                    "data": {
                        "labels": [
                            str(row.get(score_key))
                            for row in rows
                        ],
                        "datasets": [
                            {
                                "label": count_key,
                                "data": [
                                    row.get(count_key)
                                    for row in rows
                                ],
                            }
                        ],
                    },
                    "options": {
                        "indexAxis": "y",
                    },
                }

        return {}

    # ================================================================
    # NORMALIZATION
    # ================================================================

    @staticmethod
    def _normalize_query(
        text: str,
    ) -> str:

        text = text.lower().strip()

        replacements = {
            "’": "'",
            "‘": "'",
            "–": "-",
            "—": "-",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = text.replace(
            "são paulo",
            "sao paulo",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text

    # ================================================================
    # PARAMETER EXTRACTION
    # ================================================================

    def _extract_parameters(
        self,
        query: str,
    ) -> Dict[str, Any]:

        parameters: Dict[str, Any] = {}

        (
            start_date,
            end_date,
            date_specified,
        ) = self._extract_date_range(query)

        parameters[
            "date_range_specified"
        ] = date_specified

        if start_date:
            parameters["start_date"] = start_date

        if end_date:
            parameters["end_date"] = end_date

        if not date_specified:

            parameters["assumed_dataset"] = (
                "Assuming the full dataset "
                "(2016-01-01 to 2018-12-31) because "
                "no date range was specified."
            )

        state = self._extract_state(query)

        if state:
            parameters["state"] = state

        category = self._extract_category(query)

        if category:
            parameters[
                "category_name_english"
            ] = category

        limit = self._extract_limit(query)

        if limit:
            parameters["limit"] = limit

        metrics = self._extract_metrics(query)

        if metrics:
            parameters["metrics"] = metrics
            parameters["metric"] = metrics[0]

        sort = self._extract_sort(
            query,
            metrics[0] if metrics else None,
        )

        if sort:
            parameters.update(sort)

        payment_types = []
        if re.search(r"\bcredit cards?\b|\bcard payments?\b|\bcredit card\b", query):
            payment_types.append("credit_card")
        if re.search(r"\bboletos?\b", query):
            payment_types.append("boleto")
        if re.search(r"\bvouchers?\b", query):
            payment_types.append("voucher")
        if re.search(r"\bdebit cards?\b|\bdebit card\b", query):
            payment_types.append("debit_card")

        if payment_types:
            parameters["payment_types"] = payment_types

        return parameters

    # ================================================================
    # DATE EXTRACTION
    # ================================================================

    def _extract_date_range(
        self,
        query: str,
    ) -> Tuple[
        Optional[str],
        Optional[str],
        bool,
    ]:

        dates = re.findall(
            r"\b20\d{2}-\d{2}-\d{2}\b",
            query,
        )

        if len(dates) >= 2:
            return (
                dates[0],
                dates[1],
                True,
            )

        if re.search(
            r"\blast year\b",
            query,
        ):
            return (
                "2017-01-01",
                "2017-12-31",
                True,
            )

        first_half = re.search(
            r"(?:first half of|first half)\s*(20\d{2})",
            query,
        )

        if first_half:

            year = int(
                first_half.group(1)
            )

            return (
                f"{year}-01-01",
                f"{year}-06-30",
                True,
            )

        first_half_alt = re.search(
            r"\b(20\d{2})\s+first half\b",
            query,
        )

        if first_half_alt:

            year = int(
                first_half_alt.group(1)
            )

            return (
                f"{year}-01-01",
                f"{year}-06-30",
                True,
            )

        second_half = re.search(
            r"(?:second half of|second half)\s*(20\d{2})",
            query,
        )

        if second_half:

            year = int(
                second_half.group(1)
            )

            return (
                f"{year}-07-01",
                f"{year}-12-31",
                True,
            )

        second_half_alt = re.search(
            r"\b(20\d{2})\s+second half\b",
            query,
        )

        if second_half_alt:

            year = int(
                second_half_alt.group(1)
            )

            return (
                f"{year}-07-01",
                f"{year}-12-31",
                True,
            )

        h1 = re.search(
            r"\b(20\d{2})\s*h1\b",
            query,
        )

        if h1:

            year = int(
                h1.group(1)
            )

            return (
                f"{year}-01-01",
                f"{year}-06-30",
                True,
            )

        h2 = re.search(
            r"\b(20\d{2})\s*h2\b",
            query,
        )

        if h2:

            year = int(
                h2.group(1)
            )

            return (
                f"{year}-07-01",
                f"{year}-12-31",
                True,
            )

        year_match = re.search(
            r"\b(20\d{2})\b",
            query,
        )

        if year_match:

            year = int(
                year_match.group(1)
            )

            if (
                self.DATASET_START_YEAR
                <= year
                <= self.DATASET_END_YEAR
            ):

                return (
                    f"{year}-01-01",
                    f"{year}-12-31",
                    True,
                )

        return (
            None,
            None,
            False,
        )

    # ================================================================
    # STATE
    # ================================================================

    def _extract_state(
        self,
        query: str,
    ) -> Optional[str]:

        ordered_states = sorted(
            self.STATE_CODES.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for state_name, state_code in ordered_states:

            if re.search(
                rf"\b{re.escape(state_name)}\b",
                query,
            ):
                return state_code

        return None

    # ================================================================
    # CATEGORY
    # ================================================================

    def _extract_category(
        self,
        query: str,
    ) -> Optional[str]:

        categories = sorted(
            self.CATEGORY_TRANSLATIONS.keys(),
            key=len,
            reverse=True,
        )

        for category in categories:

            if re.search(
                rf"\b{re.escape(category)}\b",
                query,
            ):

                return self.CATEGORY_TRANSLATIONS[
                    category
                ]

        return None

    # ================================================================
    # LIMIT
    # ================================================================

    @staticmethod
    def _extract_limit(
        query: str,
    ) -> Optional[int]:

        match = re.search(
            r"\b(?:top|first|show|limit)\s+(\d+)\b",
            query,
        )

        if not match:
            return None

        return min(
            max(int(match.group(1)), 1),
            100,
        )

    # ================================================================
    # METRICS
    # ================================================================

    @staticmethod
    def _extract_metrics(
        query: str,
    ) -> List[str]:

        metric_patterns = {

            "revenue": [
                r"\brevenue\b",
                r"\bsales\b",
                r"\bsales value\b",
                r"\bsales amount\b",
            ],

            "orders": [
                r"\border count\b",
                r"\bnumber of orders\b",
                r"\border volume\b",
                r"\borders\b",
            ],

            "average_review_score": [
                r"\baverage review score\b",
                r"\baverage review\b",
                r"\bavg review score\b",
                r"\baverage rating\b",
                r"\bavg rating\b",
                r"\breview score\b",
                r"\bratings?\b",
                r"\bstars?\b",
                r"\breviews?\b",
            ],

            "delivery_delay": [
                r"\bfaster delivery\b",
                r"\bslower delivery\b",
                r"\bdelivery speed\b",
                r"\bdelivery delay\b",
                r"\bdelivery time\b",
                r"\bdelivery days\b",
                r"\bshipping time\b",
                r"\bshipping days\b",
            ],
        }

        found = []

        for metric, patterns in metric_patterns.items():

            for pattern in patterns:

                if re.search(
                    pattern,
                    query,
                    re.IGNORECASE,
                ):

                    if metric not in found:
                        found.append(metric)

                    break

        return found

    # ================================================================
    # SORT
    # ================================================================

    def _extract_sort(
        self,
        query: str,
        metric: Optional[str],
    ) -> Dict[str, Any]:

        if re.search(
            r"\bworst rated\b|"
            r"\blowest rated\b|"
            r"\bworst ratings\b",
            query,
        ):

            return {
                "sort_by":
                    "average_review_score",
                "sort_order":
                    "asc",
            }

        if re.search(
            r"\bbest rated\b|"
            r"\bhighest rated\b|"
            r"\bbest ratings\b",
            query,
        ):

            return {
                "sort_by":
                    "average_review_score",
                "sort_order":
                    "desc",
            }

        if re.search(
            r"\btop\b|"
            r"\bhighest\b|"
            r"\blargest\b|"
            r"\bbest\b",
            query,
        ):

            return {
                "sort_by":
                    metric or "revenue",
                "sort_order":
                    "desc",
            }

        if re.search(
            r"\blowest\b|"
            r"\bsmallest\b|"
            r"\bworst\b",
            query,
        ):

            return {
                "sort_by":
                    metric or "revenue",
                "sort_order":
                    "asc",
            }

        if re.search(
            r"\bascending\b|\basc\b",
            query,
        ):

            return {
                "sort_by":
                    metric or "revenue",
                "sort_order":
                    "asc",
            }

        if re.search(
            r"\bdescending\b|\bdesc\b",
            query,
        ):

            return {
                "sort_by":
                    metric or "revenue",
                "sort_order":
                    "desc",
            }

        return {}

    # ================================================================
    # QUERY SEMANTIC HELPERS
    # ================================================================

    @staticmethod
    def _is_score_distribution_query(
        query: str,
    ) -> bool:

        return bool(
            re.search(
                r"\bscore distribution\b|"
                r"\brating distribution\b|"
                r"\breview distribution\b|"
                r"\bdistribution of ratings\b|"
                r"\bdistribution of scores\b|"
                r"\bdistribution of customer ratings\b|"
                r"\b1[- ]5 stars?\b|"
                r"\bstars distribution\b",
                query,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _is_correlation_query(
        query: str,
    ) -> bool:

        delivery_signal = bool(
            re.search(
                r"\bfaster delivery\b|"
                r"\bslower delivery\b|"
                r"\bdelivery speed\b|"
                r"\bdelivery delay\b|"
                r"\bdelivery time\b|"
                r"\bdelivery days\b|"
                r"\bshipping time\b|"
                r"\bshipping days\b",
                query,
                re.IGNORECASE,
            )
        )

        review_signal = bool(
            re.search(
                r"\bbetter reviews?\b|"
                r"\bworse reviews?\b|"
                r"\breviews?\b|"
                r"\bratings?\b|"
                r"\breview score\b|"
                r"\baverage review\b|"
                r"\baverage rating\b",
                query,
                re.IGNORECASE,
            )
        )

        relationship_signal = bool(
            re.search(
                r"\brelationship\b|"
                r"\bcorrelation\b|"
                r"\bassociated with\b|"
                r"\bimpact\b|"
                r"\baffect\b|"
                r"\bgets?\b.*\bbetter\b|"
                r"\bget\b.*\bbetter\b",
                query,
                re.IGNORECASE,
            )
        )

        return (
            delivery_signal
            and review_signal
            and (
                relationship_signal
                or "faster delivery"
                in query
            )
        )

    @staticmethod
    def _is_multi_metric_time_query(
        query: str,
    ) -> bool:

        has_time = bool(
            re.search(
                r"\bmonthly\b|"
                r"\bweekly\b|"
                r"\byearly\b|"
                r"\bby month\b|"
                r"\bby year\b|"
                r"\bover time\b|"
                r"\btrend\b|"
                r"\btrends\b",
                query,
                re.IGNORECASE,
            )
        )

        metrics = FallbackAgent._extract_metrics(
            query
        )

        has_two_metrics = (
            len(metrics) >= 2
        )

        return (
            has_time
            and has_two_metrics
        )

    @staticmethod
    def _is_state_comparison_query(
        query: str,
    ) -> bool:

        has_state = bool(
            re.search(
                r"\bby state\b|"
                r"\bper state\b|"
                r"\bacross states\b|"
                r"\bstate wise\b",
                query,
                re.IGNORECASE,
            )
        )

        metrics = FallbackAgent._extract_metrics(
            query
        )

        return (
            has_state
            and len(metrics) >= 2
        )

    @staticmethod
    def _is_category_review_comparison_query(
        query: str,
    ) -> bool:
        """
        Detects: compare review scores across top N categories
        ranked by order volume (or similar phrasing).
        """

        has_review = bool(
            re.search(
                r"\breview scores?\b|"
                r"\baverage review\b|"
                r"\bavg review\b|"
                r"\brating scores?\b",
                query,
                re.IGNORECASE,
            )
        )

        has_category = bool(
            re.search(
                r"\bcategories?\b|"
                r"\bproduct categories?\b",
                query,
                re.IGNORECASE,
            )
        )

        has_volume_rank = bool(
            re.search(
                r"\border volume\b|"
                r"\bby orders?\b|"
                r"\bby volume\b|"
                r"\bmost ordered\b|"
                r"\bmost popular\b",
                query,
                re.IGNORECASE,
            )
        )

        return (
            has_review
            and has_category
            and has_volume_rank
        )

    @staticmethod
    def _is_state_delivery_ranking_query(
        query: str,
    ) -> bool:
        """
        Detects ranking queries about delivery performance by state.

        Must have ALL THREE:
        1. State reference (states / by state / per state)
        2. Delivery signal (delivery / shipping / delivery time / delay)
        3. Ranking language (worst / slowest / best / fastest /
           highest / lowest / top N / longest / poorest / which states)

        "show delivery delay by state" → NOT captured (no ranking language)
        "which states have the worst delivery performance?" → captured
        "top 10 states by delivery time" → captured
        """

        has_state = bool(
            re.search(
                r"\bstates?\b|"
                r"\bby state\b|"
                r"\bper state\b|"
                r"\bacross states\b",
                query,
                re.IGNORECASE,
            )
        )

        has_delivery = bool(
            re.search(
                r"\bdelivery\b|"
                r"\bdeliveries\b|"
                r"\bshipping\b|"
                r"\bdelivery time\b|"
                r"\bdelivery delay\b|"
                r"\bdelivery performance\b|"
                r"\bdelivery days\b",
                query,
                re.IGNORECASE,
            )
        )

        has_ranking = bool(
            re.search(
                r"\bworst\b|"
                r"\bslowest\b|"
                r"\blongest\b|"
                r"\bhighest\b|"
                r"\bpoorest\b|"
                r"\bbest\b|"
                r"\bfastest\b|"
                r"\bquickest\b|"
                r"\blowest\b|"
                r"\btop\s+\d+\b|"
                r"\bwhich states?\b",
                query,
                re.IGNORECASE,
            )
        )

        return has_state and has_delivery and has_ranking

    # ================================================================
    # INTENT DETECTION
    # ================================================================

    @staticmethod
    def _detect_intent(
        query: str,
    ) -> str:

        # ------------------------------------------------------------
        # Highest priority:
        # Seller delivery vs review relationship
        # ------------------------------------------------------------

        if (
            FallbackAgent._is_correlation_query(
                query
            )
        ):

            return "seller_review_correlation"

        # ------------------------------------------------------------
        # Two metrics over time
        # ------------------------------------------------------------

        if (
            FallbackAgent._is_multi_metric_time_query(
                query
            )
        ):

            return "multi_metric_time_series"

        # ------------------------------------------------------------
        # State delivery ranking
        # (before state_metric_comparison and order_trends)
        # "which states have the worst delivery performance?" → ranked_list
        # "top 10 states by delivery time" → ranked_list
        # NOT triggered by "show delivery delay by state" (no ranking word)
        # ------------------------------------------------------------

        if (
            FallbackAgent._is_state_delivery_ranking_query(
                query
            )
        ):

            return "state_delivery_ranking"

        # ------------------------------------------------------------
        # Multiple metrics by state
        # ------------------------------------------------------------

        if (
            FallbackAgent._is_state_comparison_query(
                query
            )
        ):

            return "state_metric_comparison"

        # ------------------------------------------------------------
        # Score distribution
        # IMPORTANT:
        # Only explicit distribution wording triggers this.
        # ------------------------------------------------------------

        if (
            FallbackAgent._is_score_distribution_query(
                query
            )
        ):

            return "score_distribution"

        # ------------------------------------------------------------
        # Payment
        # ------------------------------------------------------------

        if re.search(
            r"\bpayments?\b|"
            r"\bpayment methods?\b|"
            r"\bcredit cards?\b|"
            r"\bdebit cards?\b|"
            r"\bboleto\b",
            query,
            re.IGNORECASE,
        ):

            return "payment_breakdown"

        # ------------------------------------------------------------
        # Sellers
        # ------------------------------------------------------------

        if re.search(
            r"\bsellers?\b|"
            r"\bmerchants?\b|"
            r"\bvendors?\b",
            query,
            re.IGNORECASE,
        ):

            return "seller_performance"

        # ------------------------------------------------------------
        # Category review comparison (rank by orders, show review)
        # Must be checked before generic category_performance.
        # ------------------------------------------------------------

        if (
            FallbackAgent._is_category_review_comparison_query(
                query
            )
        ):

            return "category_review_comparison"

        # ------------------------------------------------------------
        # Categories
        # ------------------------------------------------------------

        if re.search(
            r"\bcategories?\b|"
            r"\bproduct categories?\b|"
            r"\bcategory performance\b",
            query,
            re.IGNORECASE,
        ):

            return "category_performance"

        # ------------------------------------------------------------
        # Reviews
        # ------------------------------------------------------------

        if re.search(
            r"\breviews?\b|"
            r"\bratings?\b|"
            r"\bcustomer feedback\b|"
            r"\bcustomer sentiment\b",
            query,
            re.IGNORECASE,
        ):

            return "customer_reviews"

        # ------------------------------------------------------------
        # Single delivery/shipping metric explicitly grouped by state
        # (without ranking language — ranking is handled above)
        # e.g. "show delivery delay by state"
        # ------------------------------------------------------------

        _has_by_state = bool(
            re.search(
                r"\bby state\b|\bper state\b|\bacross states\b|\bstate wise\b",
                query,
                re.IGNORECASE,
            )
        )
        _has_delivery_metric = bool(
            re.search(
                r"\bdelivery\b|\bdelivery delay\b|\bdelivery time\b|\bshipping\b",
                query,
                re.IGNORECASE,
            )
        )

        if _has_by_state and _has_delivery_metric:
            return "state_metric_comparison"

        # ------------------------------------------------------------
        # Default
        # ------------------------------------------------------------

        return "order_trends"

    # ================================================================
    # MCP REQUEST BUILDER
    # ================================================================

    def _date_arguments(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:

        args = {}

        if parameters.get("start_date"):
            args["start_date"] = (
                parameters["start_date"]
            )

        if parameters.get("end_date"):
            args["end_date"] = (
                parameters["end_date"]
            )

        return args

    def _build_tool_requests(
        self,
        intent: str,
        parameters: Dict[str, Any],
    ) -> List[
        Tuple[str, Dict[str, Any]]
    ]:

        date_args = self._date_arguments(
            parameters
        )

        metrics = parameters.get(
            "metrics",
            [],
        )

        # ------------------------------------------------------------
        # MULTI METRIC TIME SERIES
        # ------------------------------------------------------------

        if intent == "multi_metric_time_series":

            requests = []

            if "orders" in metrics:

                requests.append(
                    (
                        self.ORDER_TRENDS_TOOL,
                        {
                            **date_args,
                            "metric": "orders",
                            "group_by": "month",
                        },
                    )
                )

            if (
                "average_review_score"
                in metrics
            ):

                requests.append(
                    (
                        self.REVIEW_TOOL,
                        {
                            **date_args,
                            "group_by": "month",
                        },
                    )
                )

            return requests

        # ------------------------------------------------------------
        # STATE DELIVERY RANKING
        # ranked categorical: delivery time per state, no time axis
        # ------------------------------------------------------------

        if intent == "state_delivery_ranking":

            # When no date range provided, use the full dataset.
            effective_args = date_args if date_args else {
                "start_date": "2016-01-01",
                "end_date": "2018-12-31",
            }

            return [
                (
                    self.ORDER_TRENDS_TOOL,
                    {
                        **effective_args,
                        "metric": "delivery",
                        "group_by": "state",
                    },
                )
            ]

        # ------------------------------------------------------------
        # STATE METRIC COMPARISON
        # ------------------------------------------------------------

        if intent == "state_metric_comparison":

            requests = []

            if "delivery_delay" in metrics or (
                not metrics and bool(
                    re.search(r"\bdelivery\b|\bshipping\b", " ".join(parameters.get("metrics", [])) + " " + " ".join(metrics), re.IGNORECASE)
                )
            ):

                requests.append(
                    (
                        self.ORDER_TRENDS_TOOL,
                        {
                            **date_args,
                            "metric": "delivery",
                            "group_by": "state",
                        },
                    )
                )

            if "average_review_score" in metrics:

                requests.append(
                    (
                        self.REVIEW_TOOL,
                        {
                            **date_args,
                            "group_by": "state",
                        },
                    )
                )

            # Safety: if nothing was added, default to delivery by state
            if not requests:
                requests.append(
                    (
                        self.ORDER_TRENDS_TOOL,
                        {
                            **date_args,
                            "metric": "delivery",
                            "group_by": "state",
                        },
                    )
                )

            return requests

        # ------------------------------------------------------------
        # SELLER CORRELATION
        # ------------------------------------------------------------

        if intent == "seller_review_correlation":

            return [
                (
                    self.SELLER_CORRELATION_TOOL,
                    {
                        **date_args,
                    },
                )
            ]

        # ------------------------------------------------------------
        # CATEGORY REVIEW COMPARISON
        # (rank by order volume, display review score)
        # ------------------------------------------------------------

        if intent == "category_review_comparison":

            return [
                (
                    self.CATEGORY_TOOL,
                    {
                        **date_args,
                        "limit": parameters.get("limit", 5),
                        "sort_by": "orders",
                    },
                )
            ]

        # ------------------------------------------------------------
        # CATEGORY
        # ------------------------------------------------------------

        if intent == "category_performance":

            arguments = {
                "limit": parameters.get(
                    "limit",
                    10,
                ),
                "sort_by": parameters.get(
                    "sort_by",
                    "revenue",
                ),
            }

            if parameters.get(
                "category_name_english"
            ):

                arguments[
                    "category_name_english"
                ] = parameters[
                    "category_name_english"
                ]

            return [
                (
                    self.CATEGORY_TOOL,
                    arguments,
                )
            ]

        # ------------------------------------------------------------
        # SELLER
        # ------------------------------------------------------------

        if intent == "seller_performance":

            arguments = {
                "limit": parameters.get(
                    "limit",
                    10,
                ),
                "sort_order": parameters.get(
                    "sort_order",
                    "desc",
                ),
            }

            if parameters.get(
                "sort_by"
            ):

                arguments["sort_by"] = (
                    parameters["sort_by"]
                )

            if parameters.get(
                "state"
            ):

                arguments["state"] = (
                    parameters["state"]
                )

            return [
                (
                    self.SELLER_TOOL,
                    arguments,
                )
            ]

        # ------------------------------------------------------------
        # PAYMENT
        # ------------------------------------------------------------

        if intent == "payment_breakdown":
            arguments = {**date_args}
            if parameters.get("payment_types"):
                arguments["payment_types"] = parameters["payment_types"]

            return [
                (
                    self.PAYMENT_TOOL,
                    arguments,
                )
            ]

        # ------------------------------------------------------------
        # SCORE DISTRIBUTION / CUSTOMER REVIEWS
        # ------------------------------------------------------------

        if (
            intent == "score_distribution"
            or intent == "customer_reviews"
        ):

            arguments = {
                **date_args,
            }

            if parameters.get(
                "category_name_english"
            ):

                arguments[
                    "category_name_english"
                ] = parameters[
                    "category_name_english"
                ]

            if intent == "score_distribution":

                # None means distribution in
                # updated MCP server.
                arguments["group_by"] = None

            return [
                (
                    self.REVIEW_TOOL,
                    arguments,
                )
            ]

        # ------------------------------------------------------------
        # ORDER TRENDS
        # ------------------------------------------------------------

        arguments = {
            **date_args,
            "metric": parameters.get(
                "metric",
                "revenue",
            ),
        }

        return [
            (
                self.ORDER_TRENDS_TOOL,
                arguments,
            )
        ]

    # ================================================================
    # MERGE TOOL RESULTS
    # ================================================================

    def _merge_tool_results(
        self,
        datasets: List[Dict[str, Any]],
        intent: str,
    ) -> List[Dict[str, Any]]:

        if not datasets:
            return []

        # ------------------------------------------------------------
        # Seller correlation:
        # already one combined tool
        # ------------------------------------------------------------

        if intent == "seller_review_correlation":

            return self._get_rows(
                datasets[0]["data"]
            )

        # ------------------------------------------------------------
        # Single tool
        # ------------------------------------------------------------

        if len(datasets) == 1:

            return self._get_rows(
                datasets[0]["data"]
            )

        # ------------------------------------------------------------
        # Merge monthly/state datasets
        # ------------------------------------------------------------

        if intent in {
            "multi_metric_time_series",
            "state_metric_comparison",
        }:

            key = (
                "month"
                if intent
                == "multi_metric_time_series"
                else "state"
            )

            merged: Dict[
                Any,
                Dict[str, Any]
            ] = {}

            for dataset in datasets:

                rows = self._get_rows(
                    dataset["data"]
                )

                for row in rows:

                    if key not in row:
                        continue

                    group_value = row[key]

                    if (
                        group_value
                        not in merged
                    ):

                        merged[
                            group_value
                        ] = {
                            key: group_value
                        }

                    for column, value in row.items():

                        if column != key:
                            merged[
                                group_value
                            ][column] = value

            return list(
                merged.values()
            )

        return self._get_rows(
            datasets[-1]["data"]
        )

    # ================================================================
    # DATA SHAPE
    # ================================================================

    def _detect_data_shape(
        self,
        data: Any,
        tool_name: str,
        query: str,
        parameters: Dict[str, Any],
        intent: Optional[str] = None,
    ) -> str:

        rows = self._get_rows(data)

        if not rows:
            return "unknown"

        intent = (
            intent
            or self._detect_intent(query)
        )

        # ------------------------------------------------------------
        # Explicit semantic shapes FIRST
        # ------------------------------------------------------------

        if intent == "seller_review_correlation":
            return "correlation"

        if intent == "multi_metric_time_series":
            return "two_metrics_over_time"

        if intent == "state_delivery_ranking":
            return "ranked_list"

        if intent == "state_metric_comparison":
            return "category_comparison"

        if intent == "score_distribution":
            return "score_distribution"

        if intent == "category_review_comparison":
            return "category_comparison"

        if tool_name == self.PAYMENT_TOOL:
            return "part_to_whole"

        # ------------------------------------------------------------
        # Inspect actual columns
        # ------------------------------------------------------------

        columns = set()

        for row in rows:

            if isinstance(row, dict):
                columns.update(row.keys())

        numeric_columns = [
            column
            for column in self._numeric_columns(rows)
            if "id" not in column.lower()
        ]

        time_columns = {
            column
            for column in columns
            if (
                "date" in str(column).lower()
                or "month" in str(column).lower()
                or "year" in str(column).lower()
                or "period" in str(column).lower()
            )
        }

        # ------------------------------------------------------------
        # Time series
        # ------------------------------------------------------------

        if time_columns and len(
            numeric_columns
        ) >= 2:

            return "two_metrics_over_time"

        if time_columns and len(
            numeric_columns
        ) == 1:

            return "single_metric_over_time"

        # ------------------------------------------------------------
        # Intent-based overrides before column heuristics
        # ------------------------------------------------------------

        if intent == "category_performance":
            return "category_comparison"

        if intent == "seller_performance":
            return "ranked_list"

        # ------------------------------------------------------------
        # Correlation
        # ------------------------------------------------------------

        if len(numeric_columns) >= 2:

            return "two_continuous_variables"

        # ------------------------------------------------------------
        # Category comparison
        # ------------------------------------------------------------

        if (
            tool_name == self.CATEGORY_TOOL
            and len(rows) > 1
        ):

            return "category_comparison"

        # ------------------------------------------------------------
        # Ranked list
        # ------------------------------------------------------------

        if (
            tool_name == self.SELLER_TOOL
            and len(rows) > 1
        ):

            return "ranked_list"

        return "ambiguous"

    # ================================================================
    # CHART SELECTION
    # ================================================================

    def _select_chart_type(
        self,
        data_shape: str,
        raw_data: Any,
        tool_name: str,
        query: str,
        parameters: Dict[str, Any],
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:

        # ------------------------------------------------------------
        # SINGLE METRIC TIME SERIES
        # ------------------------------------------------------------

        if data_shape in {
            "single_metric_time_series",
            "single_metric_over_time",
        }:

            return {
                "chart_type": "line",
                "chart_config": {
                    "type": "line",
                    "x_axis": "time",
                    "y_axis": "metric",
                },
                "justification": (
                    "A line chart is appropriate because "
                    "one metric is measured across a time axis."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # TWO METRICS OVER TIME
        # ------------------------------------------------------------

        if data_shape == "two_metrics_over_time":

            return {
                "chart_type": "dual_axis_line",
                "chart_config": {
                    "type": "dual_axis_line",
                    "x_axis": "time",
                    "y_axes": [
                        "metric_1",
                        "metric_2",
                    ],
                },
                "justification": (
                    "A dual-axis line chart is appropriate "
                    "because two metrics are measured over "
                    "the same time axis."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # RANKED LIST
        # ------------------------------------------------------------

        if data_shape == "ranked_list":

            if intent == "state_delivery_ranking":
                return {
                    "chart_type": "horizontal_bar",
                    "chart_config": {
                        "type": "horizontal_bar",
                        "sort": "desc",
                        "orientation": "horizontal",
                    },
                    "justification": (
                        "A horizontal bar chart is appropriate "
                        "for ranking states by delivery performance "
                        "and clearly highlighting the states with "
                        "the longest delivery times."
                    ),
                    "chart_options": [],
                }

            return {
                "chart_type": "horizontal_bar",
                "chart_config": {
                    "type": "horizontal_bar",
                    "sort": "desc",
                    "orientation": "horizontal",
                },
                "justification": (
                    "A horizontal bar chart is appropriate "
                    "for comparing a ranked list of entities "
                    "by one metric."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # CATEGORY COMPARISON
        # ------------------------------------------------------------

        if data_shape == "category_comparison":

            if intent == "category_review_comparison":
                return {
                    "chart_type": "vertical_bar",
                    "chart_config": {
                        "type": "vertical_bar",
                        "orientation": "vertical",
                        "value_key": "average_review_score",
                        "label_key": "category",
                    },
                    "justification": (
                        "A vertical bar chart is appropriate "
                        "for comparing average review scores "
                        "across the top 5 product categories "
                        "ranked by order volume."
                    ),
                    "chart_options": [],
                }

            return {
                "chart_type": "vertical_bar",
                "chart_config": {
                    "type": "vertical_bar",
                    "orientation": "vertical",
                },
                "justification": (
                    "A vertical bar chart is appropriate "
                    "for comparing multiple metrics across "
                    "discrete categories or states."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # PART TO WHOLE
        # ------------------------------------------------------------

        if data_shape == "part_to_whole":

            return {
                "chart_type": "donut",
                "chart_config": {
                    "type": "donut",
                    "label_field": "category",
                    "value_field": "value",
                },
                "justification": (
                    "A donut chart is appropriate because "
                    "the data represents components of a whole."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # CORRELATION
        # ------------------------------------------------------------

        if data_shape in {
            "correlation",
            "two_continuous_variables",
        }:

            return {
                "chart_type": "scatter",
                "chart_config": {
                    "type": "scatter",
                    "x_axis": "delivery_delay",
                    "y_axis": "average_review_score",
                    "point": "seller",
                },
                "justification": (
                    "A scatter chart is appropriate because "
                    "it shows the relationship between delivery "
                    "time and average review score across sellers."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # SCORE DISTRIBUTION
        # ------------------------------------------------------------

        if data_shape == "score_distribution":

            return {
                "chart_type": "stacked_horizontal_bar",
                "chart_config": {
                    "type":
                        "stacked_horizontal_bar",
                    "x_axis": "count",
                    "y_axis": "review_score",
                    "stack": "score",
                },
                "justification": (
                    "A stacked horizontal bar chart is appropriate "
                    "because the data represents a 1–5 star score "
                    "distribution."
                ),
                "chart_options": [],
            }

        # ------------------------------------------------------------
        # AMBIGUOUS
        # ------------------------------------------------------------

        return {
            "chart_type": "ambiguous",
            "chart_config": None,
            "justification": (
                "The returned data does not uniquely determine "
                "one chart type."
            ),
            "chart_options": [
                {
                    "chart_type":
                        "horizontal_bar",
                    "reason":
                        "Useful for comparing "
                        "entities by a primary metric.",
                },
                {
                    "chart_type":
                        "vertical_bar",
                    "reason":
                        "Useful for comparing "
                        "categories or discrete groups.",
                },
            ],
        }

    # ================================================================
    # ROW HELPERS
    # ================================================================

    @staticmethod
    def _get_rows(
        data: Any,
    ) -> List[Dict[str, Any]]:

        if isinstance(data, list):

            return [
                row
                for row in data
                if isinstance(row, dict)
            ]

        if isinstance(data, dict):

            for key in (
                "data",
                "results",
                "rows",
                "records",
                "items",
            ):

                value = data.get(key)

                if isinstance(value, list):

                    return [
                        row
                        for row in value
                        if isinstance(row, dict)
                    ]

            if all(
                not isinstance(
                    value,
                    (list, dict),
                )
                for value in data.values()
            ):

                return [data]

        return []

    # ================================================================
    # NUMERIC COLUMNS
    # ================================================================

    @staticmethod
    def _numeric_columns(
        rows: List[Dict[str, Any]],
    ) -> List[str]:

        numeric_columns = []

        if not rows:
            return numeric_columns

        all_columns = set()

        for row in rows:
            all_columns.update(
                row.keys()
            )

        for column in all_columns:

            numeric_count = 0
            value_count = 0

            for row in rows:

                value = row.get(
                    column
                )

                if value is None:
                    continue

                value_count += 1

                if isinstance(
                    value,
                    (int, float),
                ) and not isinstance(
                    value,
                    bool,
                ):

                    numeric_count += 1

            if (
                value_count > 0
                and numeric_count
                / value_count
                >= 0.8
            ):

                numeric_columns.append(
                    column
                )

        return sorted(
            numeric_columns
        )

    # ================================================================
    # COLUMN HELPERS
    # ================================================================

    @staticmethod
    def _first_existing_key(
        rows: List[Dict[str, Any]],
        candidates: List[str],
    ) -> Optional[str]:

        if not rows:
            return None

        columns = set()

        for row in rows:
            columns.update(
                row.keys()
            )

        for candidate in candidates:

            if candidate in columns:
                return candidate

        return None

    @classmethod
    def _first_numeric_key(
        cls,
        rows: List[Dict[str, Any]],
        exclude: Optional[List[str]] = None,
    ) -> Optional[str]:

        exclude = exclude or []

        numeric = cls._numeric_columns(
            rows
        )

        for key in numeric:

            if key not in exclude:
                return key

        return None

    @classmethod
    def _first_label_key(
        cls,
        rows: List[Dict[str, Any]],
    ) -> Optional[str]:

        candidates = [
            "seller_id",
            "seller",
            "state",
            "category",
            "category_name",
            "payment_type",
            "payment_method",
            "review_score",
            "score",
            "month",
            "date",
        ]

        return cls._first_existing_key(
            rows,
            candidates,
        )

    # ================================================================
    # EMPTY
    # ================================================================

    @staticmethod
    def _is_empty(
        data: Any,
    ) -> bool:

        if data is None:
            return True

        if isinstance(
            data,
            (list, tuple, set, dict),
        ):

            return len(data) == 0

        return False

    # ================================================================
    # ERROR RESPONSE
    # ================================================================

    @staticmethod
    def _error_response(
        error: str,
        error_type: str,
        tool: Optional[str] = None,
        arguments: Optional[
            Dict[str, Any]
        ] = None,
        raw_data: Any = None,
    ) -> Dict[str, Any]:

        response = {
            "success": False,
            "error": error,
            "type": error_type,
        }

        if tool:
            response["tool"] = tool

        if arguments is not None:
            response[
                "tool_arguments"
            ] = arguments

        if raw_data is not None:
            response[
                "raw_data"
            ] = raw_data

        return response
