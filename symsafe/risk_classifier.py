"""
risk_classifier.py — Local keyword-based risk classification.

Provides an instant, deterministic safety net that runs before GPT.
Scans patient input for known high-risk and moderate-risk phrases
and returns a risk tier with matched flags. This ensures dangerous
symptoms are caught even if the LLM misclassifies them.

Also supports combination rules that escalate risk when multiple
symptoms appear together, even if individually they would not trigger
a high-risk classification.
"""

import json
import sqlite3

# Phrases indicating potentially life-threatening conditions.
# Organized by clinical category: cardiac, neurological, respiratory,
# vision, mental health crisis, severe trauma, and allergic reactions.
HIGH_RISK_FLAGS = [
    # Cardiac
    "chest pain", "chest tightness", "chest pressure", "heart attack", "heart racing",
    # Neurological
    "stroke", "seizure", "confusion", "can't speak", "difficulty speaking",
    "facial drooping", "worst headache", "sudden headache",
    # Respiratory
    "can't breathe", "difficulty breathing", "shortness of breath", "choking", "stopped breathing",
    # Vision
    "vision loss", "sudden blindness", "can't see",
    # Mental health crisis
    "suicidal", "want to die", "kill myself", "self-harm", "overdose",
    # Severe
    "uncontrolled bleeding", "coughing blood", "vomiting blood",
    "loss of consciousness", "passed out", "unresponsive",
    # Allergic
    "throat swelling", "anaphylaxis", "can't swallow",
]

# Phrases indicating conditions that need medical attention but are
# not immediately life-threatening.
MODERATE_RISK_FLAGS = [
    "fever", "persistent pain", "worsening symptoms", "swollen", "infected",
    "blood in stool", "blood in urine", "can't keep food down", "dehydrated",
    "sprain", "burn", "broken bone", "fracture",
]

# Combination rules define flag sets that escalate risk when ALL flags
# in the set appear together. Seeded with known medical combinations;
# clinician-approved rules from the proposals system get added at runtime.
COMBINATION_RULES = [
    {"flags": ["headache", "vision changes"], "level": "HIGH", "source": "clinical_seed"},
    {"flags": ["headache", "neck stiffness", "fever"], "level": "HIGH", "source": "clinical_seed"},
    {"flags": ["chest pain", "jaw pain"], "level": "HIGH", "source": "clinical_seed"},
    {"flags": ["chest pain", "sweating"], "level": "HIGH", "source": "clinical_seed"},
    {"flags": ["numbness", "difficulty speaking"], "level": "HIGH", "source": "clinical_seed"},
    {"flags": ["fever", "rash", "headache"], "level": "HIGH", "source": "clinical_seed"},
]

# Numeric ranking for comparing risk tiers within this module.
_TIER_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def classify_risk(user_text):
    """Classify patient input into a risk tier based on keyword matching.

    Checks HIGH-risk flags first, then MODERATE. After individual flag
    matching, checks combination rules that may escalate the risk tier
    when multiple symptoms appear together. This runs before GPT as a
    fast, deterministic pre-check.

    Args:
        user_text: The patient's message text.

    Returns:
        A tuple of (risk_level_string, matched_flags_list).
        Example: ("HIGH RISK", ["chest pain", "shortness of breath"])
    """
    text_lower = user_text.lower()

    high_matches = [flag for flag in HIGH_RISK_FLAGS if flag in text_lower]
    moderate_matches = [flag for flag in MODERATE_RISK_FLAGS if flag in text_lower]

    # Determine base tier from individual flag matches
    if high_matches:
        current_tier = "HIGH"
        matched_flags = list(high_matches)
    elif moderate_matches:
        current_tier = "MODERATE"
        matched_flags = list(moderate_matches)
    else:
        current_tier = "LOW"
        matched_flags = []

    # Check combination rules: if ALL flags in a rule appear as substrings,
    # escalate if the rule's level is higher than current classification.
    for rule in COMBINATION_RULES:
        rule_flags = rule["flags"]
        rule_level = rule["level"]

        if all(flag.lower() in text_lower for flag in rule_flags):
            if _TIER_RANK.get(rule_level, 0) > _TIER_RANK.get(current_tier, 0):
                current_tier = rule_level
                combo_desc = "combination: " + " + ".join(rule_flags)
                matched_flags.append(combo_desc)

    if current_tier == "HIGH":
        return ("\U0001f534 HIGH RISK", matched_flags)
    elif current_tier == "MODERATE":
        return ("\U0001f7e1 MODERATE RISK", matched_flags)
    return ("\U0001f7e2 LOW RISK", matched_flags)


def apply_combination_rule(rule_dict):
    """Add a new combination rule to COMBINATION_RULES at runtime.

    Args:
        rule_dict: A dict with "flags" (list of strings) and "level"
                   (risk tier string). An optional "source" key identifies
                   where the rule came from.
    """
    COMBINATION_RULES.append(rule_dict)


def load_combination_rules_from_db(db_path):
    """Load clinician-approved combination rules from the database.

    Queries the rule_proposals table for approved combination rules and
    adds each one to COMBINATION_RULES via apply_combination_rule().
    Call this at startup so approved rules persist across sessions.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT proposed_rule FROM rule_proposals "
            "WHERE status = 'approved' AND proposal_type = 'combination_rule'"
        ).fetchall()
        for row in rows:
            rule = json.loads(row["proposed_rule"])
            # Avoid adding duplicate rules
            existing_flag_sets = [
                tuple(sorted(r["flags"])) for r in COMBINATION_RULES
            ]
            new_flag_set = tuple(sorted(rule.get("flags", [])))
            if new_flag_set not in existing_flag_sets:
                apply_combination_rule({
                    "flags": rule["flags"],
                    "level": rule["level"],
                    "source": "clinician_approved",
                })
    finally:
        conn.close()
