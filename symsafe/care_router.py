"""
care_router.py — Maps risk levels to specific care recommendations.

Provides a 5-tier care routing system (emergency, urgent_care, primary_care,
telehealth, self_care) with actionable guidance for each level. Includes
safety-first merging logic that ensures care recommendations are never
downgraded below what the risk level warrants.
"""

# Numeric ranking used to compare care levels. Higher values indicate
# more urgent care. Used by merge_care_level() to enforce minimum thresholds.
CARE_LEVEL_HIERARCHY = {
    "self_care": 0,
    "telehealth": 1,
    "primary_care": 2,
    "urgent_care": 3,
    "emergency": 4,
}

# Actionable guidance for each care tier. Each entry provides three fields:
# where (location/action), why (rationale), and right_now (immediate steps).
CARE_GUIDANCE = {
    "emergency": {
        "where": "Call 911 or go to your nearest emergency room immediately.",
        "why": "These symptoms could indicate a life-threatening condition that needs immediate evaluation.",
        "right_now": "Do not drive yourself. Call 911 or have someone take you. If you're alone, call 911 — they can help you over the phone while help is on the way.",
    },
    "urgent_care": {
        "where": "Visit an urgent care clinic or walk-in clinic today.",
        "why": "This needs medical attention today, but an urgent care clinic can handle it — you don't need an emergency room, which will save you time and money.",
        "right_now": "Rest and avoid strenuous activity. Write down your symptoms and when they started so you can tell the provider.",
    },
    "primary_care": {
        "where": "Schedule an appointment with your primary care doctor this week.",
        "why": "This is worth getting checked out, but it's not urgent enough to need same-day care.",
        "right_now": "Keep track of your symptoms — note when they happen, how severe they are, and anything that makes them better or worse. This will help your doctor.",
    },
    "telehealth": {
        "where": "Consider a telehealth or virtual visit — you can often get seen today without leaving home.",
        "why": "Your symptoms can likely be evaluated through a video visit, which is convenient and often less expensive.",
        "right_now": "Write down your symptoms and any medications you're taking so you're ready for the call.",
    },
    "self_care": {
        "where": "You can monitor this at home for now.",
        "why": "Based on what you've described, this doesn't seem to need medical attention right now.",
        "right_now": "Rest, stay hydrated, and keep an eye on your symptoms. If anything gets worse or new symptoms develop, check back in or see a healthcare provider.",
    },
}


def get_care_guidance(care_level):
    """Look up actionable care guidance for a given care level.

    Args:
        care_level: One of "emergency", "urgent_care", "primary_care",
                    "telehealth", or "self_care".

    Returns:
        A dict with 'where', 'why', and 'right_now' keys.
        Defaults to self_care guidance for unrecognized levels.
    """
    return CARE_GUIDANCE.get(care_level, CARE_GUIDANCE["self_care"])


def merge_care_level(local_risk_level, gpt_care_level):
    """Merge GPT's care recommendation with the local risk assessment.

    Applies safety-first logic: if the local risk classifier flagged a
    higher severity than GPT's care level implies, the care level is
    upgraded to match. Emergency is never downgraded regardless of source.

    Rules:
        - HIGH risk forces at least urgent_care
        - MODERATE risk forces at least primary_care
        - LOW risk trusts GPT's recommendation as-is
        - Emergency from GPT is always preserved

    Args:
        local_risk_level: The emoji-prefixed risk string from classify_risk().
        gpt_care_level: The care level string from GPT's structured output.

    Returns:
        The final care level string after safety-first merging.
    """
    if gpt_care_level not in CARE_LEVEL_HIERARCHY:
        gpt_care_level = "self_care"

    # Never downgrade emergency
    if gpt_care_level == "emergency":
        return "emergency"

    risk_upper = local_risk_level.upper()

    if "HIGH" in risk_upper:
        if CARE_LEVEL_HIERARCHY.get(gpt_care_level, 0) < CARE_LEVEL_HIERARCHY["urgent_care"]:
            return "urgent_care"
        return gpt_care_level

    if "MODERATE" in risk_upper:
        if CARE_LEVEL_HIERARCHY.get(gpt_care_level, 0) < CARE_LEVEL_HIERARCHY["primary_care"]:
            return "primary_care"
        return gpt_care_level

    # LOW risk — trust GPT's assessment
    return gpt_care_level
