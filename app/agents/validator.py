import re
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("analytics_chatbot")

# Supported intent patterns and keywords
SUPPORTED_ANALYTICS_PATTERNS = [
    # Revenue / Sales trends
    r"\brevenue\b", r"\bsales\b", r"\bearnings\b", r"\bincome\b", r"\bfinancial\b",
    
    # Orders / Volume
    r"\borders?\b", r"\border count\b", r"\border volume\b", r"\bvolume\b", r"\bpurchases?\b",
    
    # Product categories
    r"\bcategor(y|ies)\b", r"\bproduct(s)?\b", r"\belectronics\b", r"\bcomputers?\b",
    r"\bfurniture\b", r"\bappliances?\b", r"\bfashion\b", r"\bclothing\b",
    r"\bsports?\b", r"\btoys?\b", r"\bbooks?\b", r"\bhealth\b", r"\bbeauty\b",
    r"\bautomotive\b", r"\bgarden\b",
    
    # Sellers / Merchants
    r"\bsellers?\b", r"\bmerchants?\b", r"\bvendors?\b",
    
    # Payments
    r"\bpayments?\b", r"\bcredit card(s)?\b", r"\bboleto(s)?\b", r"\bvoucher(s)?\b",
    r"\bdebit card(s)?\b", r"\bpayment method(s)?\b",
    
    # Reviews / Scores / Ratings
    r"\breviews?\b", r"\bratings?\b", r"\bscores?\b", r"\bstars?\b", r"\bfeedback\b", r"\bsentiment\b",
    
    # Delivery / Shipping
    r"\bdelivery\b", r"\bdeliveries\b", r"\bshipping\b", r"\bshipment\b", r"\bdelay(s)?\b", r"\bfreight\b",
    
    # States
    r"\bstates?\b", r"\bsao paulo\b", r"\brio de janeiro\b", r"\bminas gerais\b",
    
    # Analytics indicators combined with time/ranking/distribution
    r"\btrend(s)?\b", r"\bmonthly\b", r"\byearly\b", r"\bweekly\b", r"\bover time\b",
    r"\bdistribution\b", r"\bcorrelation\b", r"\brelationship\b", r"\bbreakdown\b",
    r"\bperformance\b", r"\branking\b", r"\bworst\b", r"\bbest\b", r"\btop\b", r"\bhighest\b", r"\blowest\b",
    r"\bshare\b", r"\bpercentage\b"
]

UNSUPPORTED_EXPLICIT_GIBBERISH = {
    "gloe", "asdfgh", "hello123", "xyz", "random text", "abc", "test", "asdf", "qwerty", "foo", "bar"
}

def validate_user_intent(query_str: str) -> Tuple[bool, str, float]:
    """
    Validates if a query string contains a supported analytical intent.
    Returns: (is_valid: bool, detected_intent: str, confidence: float)
    """
    if not query_str or not isinstance(query_str, str):
        return False, "unsupported", 0.0

    normalized = query_str.strip().lower()

    if not normalized or normalized in UNSUPPORTED_EXPLICIT_GIBBERISH:
        return False, "unsupported", 0.0

    # Count matching patterns
    matched_patterns = []
    for pattern in SUPPORTED_ANALYTICS_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            matched_patterns.append(pattern)

    if not matched_patterns:
        return False, "unsupported", 0.0

    # Specific intent categorization logic
    if re.search(r"\bfaster delivery\b|\bslower delivery\b|\bdelivery delay\b.*(review|rating)", normalized) or (
        "delivery" in normalized and ("review" in normalized or "rating" in normalized or "score" in normalized)
    ):
        return True, "seller_review_correlation", 0.95

    if re.search(r"\bscore distribution\b|\brating distribution\b|\breview distribution\b|1[- ]5 star", normalized):
        return True, "score_distribution", 0.95

    if re.search(r"\bpayment\b|\bcredit card\b|\bboleto\b|\bvoucher\b|\bdebit card\b", normalized):
        return True, "payment_breakdown", 0.95

    if re.search(r"\bcategor(y|ies)\b|\bproduct categories\b", normalized):
        return True, "category_performance", 0.90

    if re.search(r"\bsellers?\b|\bmerchants?\b", normalized):
        return True, "seller_performance", 0.90

    if re.search(r"\bstates?\b.*(delivery|delay|worst|best)", normalized):
        return True, "state_delivery_ranking", 0.90

    if re.search(r"\brevenue\b|\bsales\b|\borders?\b|\btrend(s)?\b|\bmonthly\b", normalized):
        return True, "monthly_revenue_trend", 0.90

    if re.search(r"\breviews?\b|\bratings?\b", normalized):
        return True, "customer_reviews", 0.85

    # General supported analytical query
    confidence = min(0.5 + len(matched_patterns) * 0.15, 0.95)
    return True, "general_analytics", confidence
