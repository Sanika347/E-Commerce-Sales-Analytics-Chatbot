import json
from google import genai
from app.config import settings

def generate_insight_llm(data: list[dict], user_query: str) -> str:
    """Uses Gemini to generate a single-sentence business insight."""
    if not data:
        return "No data available to generate an insight."
        
    # Truncate data if too long
    truncated_data = data[:20]
    data_str = json.dumps(truncated_data)
    
    prompt = f"""
    You are an expert e-commerce data analyst. Look at the following JSON data representing the answer to the user query: "{user_query}"
    
    Data:
    {data_str}
    
    Write EXACTLY ONE sentence explaining the most important business takeaway from this data. 
    Do not use markdown. Do not hallucinate metrics not present.
    """
    try:
        if not settings.gemini_api_key:
            return generate_insight_fallback(data, user_query)
            
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model='gemini-1.5-pro',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error generating insight: {e}")
        return generate_insight_fallback(data, user_query)

def generate_insight_fallback(data: list[dict], user_query: str) -> str:
    """Fallback insight generation when LLM is unavailable or in fallback mode."""
    if data and isinstance(data, list) and isinstance(data[0], dict):
        keys = data[0].keys()
        delay_key = next((k for k in ['avg_delivery_delay', 'delivery_delay'] if k in keys), None)
        score_key = next((k for k in ['avg_review_score', 'average_review_score'] if k in keys), None)
        
        if delay_key and score_key:
            entity_key = 'seller_id' if 'seller_id' in keys else ('state' if 'state' in keys else 'entity')
            entity_name = "sellers" if entity_key == 'seller_id' else ("states" if entity_key == 'state' else "items")
            
            delays = []
            scores = []
            for row in data:
                d = row.get(delay_key)
                s = row.get(score_key)
                if d is not None and s is not None:
                    try:
                        delays.append(float(d))
                        scores.append(float(s))
                    except (ValueError, TypeError):
                        pass
                        
            if entity_key == 'state' and delays and scores:
                n = len(delays)
                max_delay_idx = delays.index(max(delays))
                min_delay_idx = delays.index(min(delays))
                worst_state = data[max_delay_idx].get('state', 'Unknown')
                best_state = data[min_delay_idx].get('state', 'Unknown')
                return f"Across {n} states, average delivery delay ranges from {min(delays):.1f} days ({best_state}) to {max(delays):.1f} days ({worst_state}), while average review scores range from {min(scores):.2f} to {max(scores):.2f} stars."
        elif keys and 'state' in keys and 'delivery_delay' in keys:
            delays = [float(row.get('delivery_delay', 0)) for row in data if row.get('delivery_delay') is not None]
            if delays:
                worst_row = max(data, key=lambda x: float(x.get('delivery_delay', 0)))
                worst_state = worst_row.get('state', 'Unknown')
                worst_delay = worst_row.get('delivery_delay', 0)
                return f"State {worst_state} has the worst delivery performance with an average delivery delay of {worst_delay:.1f} days across the dataset."
                
            if entity_key == 'seller_id' and len(delays) > 2:
                n = len(delays)
                mean_d = sum(delays) / n
                mean_s = sum(scores) / n
                num = sum((d - mean_d) * (s - mean_s) for d, s in zip(delays, scores))
                den_d = (sum((d - mean_d) ** 2 for d in delays)) ** 0.5
                den_s = (sum((s - mean_s) ** 2 for s in scores)) ** 0.5
                if den_d > 0 and den_s > 0:
                    r = num / (den_d * den_s)
                    if r < -0.3:
                        relationship = "a negative relationship (sellers with longer delivery delays tend to have lower review scores)"
                    elif r > 0.3:
                        relationship = "a positive relationship (sellers with longer delivery delays tend to have higher review scores)"
                    else:
                        relationship = "little to no linear relationship between delivery delay and review score"
                    return f"Across {n} sellers (Pearson r = {r:.2f}), the data shows {relationship}."

        if 'payment_type' in keys:
            PAYMENT_LABEL_MAP = {
                "credit_card": "credit card",
                "boleto": "boleto",
                "voucher": "voucher",
                "debit_card": "debit card",
                "not_defined": "not defined"
            }
            if len(data) == 2:
                t1 = PAYMENT_LABEL_MAP.get(str(data[0].get('payment_type')), str(data[0].get('payment_type')))
                s1 = data[0].get('share', data[0].get('count', 0))
                t2 = PAYMENT_LABEL_MAP.get(str(data[1].get('payment_type')), str(data[1].get('payment_type')))
                s2 = data[1].get('share', data[1].get('count', 0))
                if 'share' in data[0]:
                    return f"Among {t1} and {t2} payments, {t1}s account for {s1}% while {t2}s account for {s2}%."
            top_pt = PAYMENT_LABEL_MAP.get(str(data[0].get('payment_type')), str(data[0].get('payment_type')))
            top_share = data[0].get('share', '')
            share_str = f" ({top_share}%)" if top_share else ""
            return f"The most common payment method is {top_pt}{share_str}."

        if data and isinstance(data, list) and len(data) > 0:
            return f"Analyzed {len(data)} records for the requested metric."

    return "No data available."
