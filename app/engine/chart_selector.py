import re

def determine_chart_type(data: list[dict], tool_name: str, user_query: str = "") -> tuple[dict, str]:
    """
    Determine Chart.js type based on data shape and tool name.
    Returns (chart_config, justification).
    """
    if not data:
        return {}, "No data to visualize."

    keys = list(data[0].keys())
    
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

    if tool_name == 'get_seller_delivery_review_correlation':
        points = []
        for row in data:
            delay = row.get('avg_delivery_delay') or row.get('delivery_delay')
            score = row.get('avg_review_score') or row.get('average_review_score')
            if delay is not None and score is not None:
                try:
                    points.append({"x": float(delay), "y": float(score)})
                except (ValueError, TypeError):
                    continue
        config = {
            "type": "scatter",
            "data": {
                "datasets": [{
                    "label": "Sellers",
                    "data": points,
                    "backgroundColor": "rgba(54, 162, 235, 0.7)"
                }]
            },
            "options": {
                "responsive": True,
                "scales": {
                    "x": {
                        "type": "linear",
                        "title": {
                            "display": True,
                            "text": "Average Delivery Delay (Days)"
                        }
                    },
                    "y": {
                        "title": {
                            "display": True,
                            "text": "Average Review Score (Stars)"
                        },
                        "min": 1,
                        "max": 5
                    }
                }
            }
        }
        return config, "A scatter plot is appropriate because it shows the relationship between average delivery delay and average review score across sellers. Each point represents one seller."

    if tool_name == 'get_payment_breakdown':
        PAYMENT_LABEL_MAP = {
            "credit_card": "Credit Card",
            "boleto": "Boleto",
            "voucher": "Voucher",
            "debit_card": "Debit Card",
            "not_defined": "Not Defined"
        }
        labels = [PAYMENT_LABEL_MAP.get(str(row['payment_type']), str(row['payment_type']).replace("_", " ").title()) for row in data]
        val_key = 'share' if 'share' in keys else 'count'
        values = [row[val_key] for row in data]
        metric_label = "Payment Share (%)" if val_key == 'share' else "Payment Count"
        config = {
            "type": "doughnut",
            "data": {
                "labels": labels,
                "datasets": [{"label": metric_label, "data": values}]
            }
        }
        if len(data) == 2:
            justification = f"A doughnut chart is appropriate because the user is comparing the share of two payment methods ({labels[0]} vs {labels[1]}) as parts of the total selected payment methods."
        else:
            justification = "A doughnut chart is appropriate because the data represents a part-to-whole relationship across payment type shares."
        return config, justification
        
    if tool_name == 'get_customer_reviews':
        labels = [f"{row['review_score']} Star" for row in data]
        values = [row['count'] for row in data]
        config = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [{"label": "Review Count", "data": values, "backgroundColor": "#4CAF50"}]
            },
            "options": {
                "indexAxis": "y",
                "scales": {"x": {"stacked": True}, "y": {"stacked": True}}
            }
        }
        return config, "Stacked horizontal bar chart chosen because the data represents a score distribution (1-5 stars)."
        
    if tool_name == 'get_seller_performance':
        labels = [str(row.get('seller_id', 'Unknown'))[:8] for row in data] 
        values = [row['total_revenue'] for row in data]
        config = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [{"label": "Revenue (BRL)", "data": values}]
            },
            "options": {
                "indexAxis": "y"
            }
        }
        return config, "Horizontal bar chart chosen because the data is a ranked list (top sellers by revenue)."
        
    def determine_requested_metric(query_str: str, rows: list[dict]) -> str | None:
        query_lower = query_str.lower() if query_str else ""
        keys_set = set()
        for row in rows:
            if isinstance(row, dict):
                keys_set.update(row.keys())

        if re.search(r'\brevenue\b|\bsales\b|\bsales value\b|\bsales amount\b', query_lower):
            if 'total_revenue' in keys_set:
                return 'total_revenue'
            if 'revenue' in keys_set:
                return 'revenue'

        if re.search(r'\bfreight\b|\bshipping cost\b|\bfreight value\b', query_lower):
            if 'avg_freight' in keys_set:
                return 'avg_freight'
            if 'freight' in keys_set:
                return 'freight'

        if re.search(r'\breview score\b|\baverage review\b|\baverage rating\b|\brating\b', query_lower):
            if 'avg_review_score' in keys_set:
                return 'avg_review_score'
            if 'average_review_score' in keys_set:
                return 'average_review_score'

        if re.search(r'\border count\b|\bnumber of orders\b|\border volume\b|\borders\b', query_lower):
            if 'order_volume' in keys_set:
                return 'order_volume'
            if 'order_count' in keys_set:
                return 'order_count'
            if 'orders' in keys_set:
                return 'orders'

        # Fallback based on keys presence
        for k in ['total_revenue', 'revenue', 'order_volume', 'avg_review_score', 'average_review_score', 'avg_freight']:
            if k in keys_set:
                return k

        return None

    if tool_name == 'get_product_category_performance':
        req_metric = determine_requested_metric(user_query, data) or ('total_revenue' if 'total_revenue' in keys else keys[1] if len(keys)>1 else keys[0])
        labels = [str(row.get('category', 'Unknown')) for row in data]
        values = [row.get(req_metric, 0) for row in data]
        
        is_revenue = req_metric in ['total_revenue', 'revenue']
        chart_type = "bar"
        index_axis = "y" if is_revenue else "x"
        
        config = {
            "type": chart_type,
            "data": {
                "labels": labels,
                "datasets": [{"label": clean_label(req_metric), "data": values, "backgroundColor": "#36A2EB"}]
            },
            "options": {
                "indexAxis": index_axis,
                "scales": {
                    "x": {"title": {"display": True, "text": clean_label(req_metric) if is_revenue else "Product Category"}},
                    "y": {"title": {"display": True, "text": "Product Category" if is_revenue else clean_label(req_metric)}}
                }
            }
        }
        
        if is_revenue:
            justification = f"A horizontal bar chart is appropriate for ranking product categories by total revenue and clearly showing which categories generate the most revenue."
        else:
            justification = f"A bar chart is appropriate for ranking product categories by {clean_label(req_metric)}."
            
        return config, justification
        
    # Check for multi-metric comparison (e.g., side by side state metrics: delivery delay & review score)
    label_key = keys[0]
    numeric_keys = [k for k in keys if k != label_key and isinstance(data[0].get(k), (int, float))]
    
    if len(numeric_keys) >= 2:
        m1, m2 = numeric_keys[0], numeric_keys[1]
        labels = [str(row[label_key]) for row in data]
        config = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": clean_label(m1),
                        "data": [row.get(m1) for row in data],
                        "yAxisID": "y",
                        "backgroundColor": "rgba(54, 162, 235, 0.7)"
                    },
                    {
                        "label": clean_label(m2),
                        "data": [row.get(m2) for row in data],
                        "yAxisID": "y1",
                        "backgroundColor": "rgba(255, 99, 132, 0.7)"
                    }
                ]
            },
            "options": {
                "responsive": True,
                "scales": {
                    "x": {
                        "display": True,
                        "title": {"display": True, "text": clean_label(label_key)}
                    },
                    "y": {
                        "type": "linear",
                        "position": "left",
                        "title": {"display": True, "text": clean_label(m1)}
                    },
                    "y1": {
                        "type": "linear",
                        "position": "right",
                        "title": {"display": True, "text": clean_label(m2)},
                        "grid": {"drawOnChartArea": False}
                    }
                }
            }
        }
        return config, "A dual-axis bar chart is appropriate for comparing multiple metrics across discrete categories or states."

    if tool_name == 'get_order_trends':
        time_label_key = 'month' if 'month' in keys else ('state' if 'state' in keys else keys[0])
        
        # Check if this is a state delivery ranking query (e.g., group_by state and metric is delivery delay)
        if time_label_key == 'state' or 'delivery_delay' in keys or re.search(r'\bstates?\b', user_query.lower() if user_query else ""):
            if 'state' in keys:
                metric_key = 'delivery_delay' if 'delivery_delay' in keys else ([k for k in keys if k != 'state' and isinstance(data[0].get(k), (int, float))] + ['delivery_delay'])[0]
                # Sort descending by delivery delay so worst state is at top
                sorted_data = sorted(data, key=lambda x: float(x.get(metric_key) or 0), reverse=False) # In Chart.js horizontal bar (indexAxis: y), index 0 is at bottom, so reverse=False puts highest value at the top of the visual chart!
                # Wait: let's verify Chart.js indexAxis: 'y' ordering! In Chart.js horizontal bar charts, categories are listed top-to-bottom matching array index order (0 at top, or bottom depending on y scale reverse).
                # Actually, in standard Chart.js y-axis category scale, index 0 is at top!
                # Let's sort reverse=True so highest value (worst delivery delay) is index 0 (top of chart).
                sorted_data = sorted(data, key=lambda x: float(x.get(metric_key) or 0), reverse=True)
                labels = [str(row.get('state', '')) for row in sorted_data]
                values = [row.get(metric_key, 0) for row in sorted_data]
                config = {
                    "type": "bar",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": clean_label(metric_key),
                            "data": values,
                            "backgroundColor": "rgba(255, 99, 132, 0.7)"
                        }]
                    },
                    "options": {
                        "indexAxis": "y",
                        "responsive": True,
                        "scales": {
                            "x": {
                                "display": True,
                                "title": {"display": True, "text": clean_label(metric_key)}
                            },
                            "y": {
                                "display": True,
                                "title": {"display": True, "text": "State"}
                            }
                        }
                    }
                }
                return config, "A horizontal bar chart is appropriate for ranking states by average delivery time, with the longest delivery times shown first."

        labels = [str(row.get(time_label_key, '')) for row in data]
        metric_key_candidates = [k for k in keys if k != time_label_key and isinstance(data[0].get(k), (int, float))]
        metric_key = metric_key_candidates[0] if metric_key_candidates else keys[-1]
        values = [row.get(metric_key, 0) for row in data]
        config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": clean_label(metric_key),
                    "data": values,
                    "fill": False,
                    "borderColor": "#2196F3",
                    "tension": 0.1
                }]
            },
            "options": {
                "responsive": True,
                "scales": {
                    "x": {
                        "display": True,
                        "title": {"display": True, "text": "Month"},
                        "ticks": {"autoSkip": False, "maxRotation": 45, "minRotation": 0}
                    },
                    "y": {
                        "display": True,
                        "title": {"display": True, "text": clean_label(metric_key)}
                    }
                }
            }
        }
        return config, "A line chart is appropriate for displaying single-metric continuous time series trends over monthly intervals."

    labels = [str(row[keys[0]]) for row in data]
    values = [row[keys[1]] for row in data] if len(keys) > 1 else [1]*len(data)
    
    config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{"label": clean_label(keys[1]) if len(keys) > 1 else "Value", "data": values}]
        }
    }
    return config, "Bar chart chosen as the default fallback for this data shape."
