"""
feedback.py — Gap detection, proposal generation, and synonym application.

Compares local keyword classifier results against GPT risk assessments to
identify cases where GPT catches risks that the local classifier misses.
When gaps are found, generates structured proposals for new synonyms or
rules that a clinician can review and approve.

Also handles applying approved synonyms back into risk_classifier.py on
disk, detecting combination patterns across clinician-corrected exchanges,
and generating rule proposals for recurring symptom combinations.
"""

import datetime
import json
import re
import sqlite3
from collections import Counter

from symsafe.config import DB_PATH


def detect_classifier_gap(user_input, local_risk_level, local_risk_flags,
                          gpt_risk_level, gpt_risk_flags):
    """Compare local vs GPT classification and identify missed risks.

    A gap exists when GPT flagged the input as HIGH or MODERATE risk but the
    local keyword classifier returned LOW. This indicates a phrase or pattern
    that the local classifier should learn to recognize.

    Args:
        user_input: The patient's original message text.
        local_risk_level: Risk level string from the local classifier
                          (e.g. "LOW RISK").
        local_risk_flags: List of flags matched by the local classifier.
        gpt_risk_level: Risk level string from GPT (e.g. "HIGH").
        gpt_risk_flags: List of risk flags identified by GPT.

    Returns:
        A dict describing the gap with keys: patient_phrase, gpt_risk_level,
        local_risk_level, gpt_flags. Returns None if there is no gap (both
        agree, or local was more cautious than GPT).
    """
    local_tier = _extract_tier(local_risk_level)
    gpt_tier = _extract_tier(gpt_risk_level)

    tier_rank = {"LOW": 0, "MODERATE": 1, "HIGH": 2}

    if local_tier != "LOW":
        return None
    if tier_rank.get(gpt_tier, 0) <= tier_rank.get(local_tier, 0):
        return None

    missed_flags = [f for f in gpt_risk_flags if f not in local_risk_flags]

    return {
        "patient_phrase": user_input,
        "gpt_risk_level": gpt_tier,
        "local_risk_level": local_tier,
        "gpt_flags": missed_flags if missed_flags else gpt_risk_flags,
    }


def find_nearest_flag(phrase, flag_list):
    """Find the most similar existing flag to a patient phrase.

    Uses word-level overlap to identify which existing flag in the classifier's
    list is closest to the patient's phrasing. This enables proposals like
    "add 'chest is burning' as synonym for 'chest pain'" rather than orphaned
    additions.

    Args:
        phrase: The patient's phrase to match against existing flags.
        flag_list: List of existing flag strings (e.g. HIGH_RISK_FLAGS).

    Returns:
        The best matching flag string, or None if no meaningful overlap exists.
    """
    if not phrase or not flag_list:
        return None

    phrase_words = set(phrase.lower().split())
    best_match = None
    best_score = 0

    for flag in flag_list:
        flag_words = set(flag.lower().split())
        overlap = len(phrase_words & flag_words)
        if overlap > best_score:
            best_score = overlap
            best_match = flag

    if best_score == 0:
        return None
    return best_match


def save_synonym_proposal(db_path, patient_phrase, gpt_risk_level,
                          local_risk_level, proposed_category,
                          proposed_synonym_for, session_id):
    """Insert a synonym proposal into the database for clinician review.

    Args:
        db_path: Path to the SQLite database file. Uses DB_PATH if None.
        patient_phrase: The patient's original phrase that was missed.
        gpt_risk_level: What GPT classified it as ("HIGH" or "MODERATE").
        local_risk_level: What the local classifier said (usually "LOW").
        proposed_category: Which flag list it should be added to ("HIGH" or "MODERATE").
        proposed_synonym_for: The nearest existing flag (e.g. "chest pain").
        session_id: Which session this proposal came from.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """INSERT INTO synonym_proposals
               (patient_phrase, gpt_risk_level, local_risk_level,
                proposed_category, proposed_synonym_for, session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_phrase,
                gpt_risk_level,
                local_risk_level,
                proposed_category,
                proposed_synonym_for,
                session_id,
                datetime.datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_proposals(db_path, proposal_type="synonym"):
    """Retrieve all pending proposals of a given type.

    Args:
        db_path: Path to the SQLite database file.
        proposal_type: Either "synonym" for synonym_proposals table or
                       "rule" for rule_proposals table.

    Returns:
        A list of dicts representing pending proposals.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if proposal_type == "synonym":
            rows = conn.execute(
                "SELECT * FROM synonym_proposals WHERE status = 'pending'"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM rule_proposals WHERE status = 'pending'"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve_synonym(db_path, proposal_id, reviewer="clinician"):
    """Mark a synonym proposal as approved.

    Does NOT modify risk_classifier.py automatically. Call
    apply_approved_synonyms() separately to write approved synonyms
    into the classifier source file.

    Args:
        db_path: Path to the SQLite database file.
        proposal_id: The auto-incremented ID of the synonym proposal.
        reviewer: Name or identifier of the reviewing clinician.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE synonym_proposals SET status = 'approved', reviewed_by = ? WHERE id = ?",
            (reviewer, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()


def reject_proposal(db_path, proposal_id, reviewer="clinician"):
    """Mark any proposal (synonym or rule) as rejected.

    Args:
        db_path: Path to the SQLite database file.
        proposal_id: The auto-incremented ID of the proposal.
        reviewer: Name or identifier of the reviewing clinician.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE synonym_proposals SET status = 'rejected', reviewed_by = ? WHERE id = ?",
            (reviewer, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()


def apply_approved_synonyms(db_path, classifier_path):
    """Write approved synonym proposals into risk_classifier.py on disk.

    Reads all synonym proposals with status="approved", checks if each
    phrase already exists in the target flag list, and inserts new ones
    into the source file. After writing, marks each proposal as "applied"
    in the database.

    Args:
        db_path: Path to the SQLite database file.
        classifier_path: Path to risk_classifier.py on disk.

    Returns:
        A list of dicts describing what was applied. Each dict has keys:
        "phrase", "added_to", "synonym_for". Returns an empty list if
        no approved proposals exist or all were already present.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM synonym_proposals WHERE status = 'approved'"
        ).fetchall()
        proposals = [dict(r) for r in rows]
    finally:
        conn.close()

    if not proposals:
        return []

    source = _read_file(classifier_path)
    applied = []

    for proposal in proposals:
        phrase = proposal["patient_phrase"].lower().strip()
        category = proposal.get("proposed_category", "HIGH").upper()

        if category == "HIGH":
            list_name = "HIGH_RISK_FLAGS"
        else:
            list_name = "MODERATE_RISK_FLAGS"

        # Check if the phrase already exists in the file
        if f'"{phrase}"' in source or f"'{phrase}'" in source:
            # Already present, just mark as applied
            _mark_proposal_applied(db_path, proposal["id"])
            continue

        # Find the closing bracket of the target list and insert before it
        source = _insert_into_flag_list(source, list_name, phrase)
        applied.append({
            "phrase": phrase,
            "added_to": category,
            "synonym_for": proposal.get("proposed_synonym_for"),
        })
        _mark_proposal_applied(db_path, proposal["id"])

    if applied:
        _write_file(classifier_path, source)

    return applied


def detect_combination_patterns(db_path, min_occurrences=3):
    """Find symptom combinations that clinicians consistently escalate.

    Queries all exchanges where review_status="corrected" and the corrected
    risk level is higher than the original. Groups by the sorted set of risk
    flags and returns patterns that appear in min_occurrences or more
    corrections.

    Args:
        db_path: Path to the SQLite database file.
        min_occurrences: Minimum number of corrections needed to propose
                         a combination rule. Defaults to 3.

    Returns:
        A list of dicts, each with keys: "flags" (sorted list), "proposed_level",
        "occurrences" (int), "session_ids" (list of session ID strings).
        Returns an empty list if no patterns meet the threshold.
    """
    tier_rank = {"LOW": 0, "MODERATE": 1, "HIGH": 2}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM exchanges WHERE review_status = 'corrected'"
        ).fetchall()
    finally:
        conn.close()

    # Group corrections by flag combination
    combo_data = {}
    for row in rows:
        row_dict = dict(row)
        corrected_level = _extract_tier(row_dict.get("corrected_risk_level", ""))
        merged_level = _extract_tier(row_dict.get("merged_risk_level", ""))

        # Only consider corrections where risk was escalated
        if tier_rank.get(corrected_level, 0) <= tier_rank.get(merged_level, 0):
            continue

        # Parse flags from the stored JSON
        try:
            local_flags = json.loads(row_dict.get("local_risk_flags", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            local_flags = []
        try:
            gpt_flags = json.loads(row_dict.get("gpt_risk_flags", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            gpt_flags = []

        all_flags = sorted(set(local_flags + gpt_flags))

        # Skip single-flag combinations (those are synonym issues)
        if len(all_flags) < 2:
            continue

        combo_key = tuple(all_flags)
        if combo_key not in combo_data:
            combo_data[combo_key] = {
                "flags": list(combo_key),
                "proposed_level": corrected_level,
                "session_ids": [],
            }
        combo_data[combo_key]["session_ids"].append(row_dict.get("session_id", ""))

    # Filter by minimum occurrences
    results = []
    for combo_key, data in combo_data.items():
        if len(data["session_ids"]) >= min_occurrences:
            results.append({
                "flags": data["flags"],
                "proposed_level": data["proposed_level"],
                "occurrences": len(data["session_ids"]),
                "session_ids": data["session_ids"],
            })

    return results


def save_rule_proposal(db_path, proposal_type, description,
                       supporting_evidence, proposed_rule):
    """Insert a rule proposal into the rule_proposals table.

    Args:
        db_path: Path to the SQLite database file.
        proposal_type: Type of rule ("combination_rule" or "escalation_rule").
        description: Human-readable description of the proposed rule.
        supporting_evidence: JSON-serializable data (list of session IDs).
        proposed_rule: JSON-serializable dict defining the rule.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO rule_proposals
               (proposal_type, description, supporting_evidence,
                proposed_rule, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                proposal_type,
                description,
                json.dumps(supporting_evidence),
                json.dumps(proposed_rule),
                datetime.datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_rule_proposals(db_path):
    """Return all rule proposals with status="pending".

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A list of dicts representing pending rule proposals.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM rule_proposals WHERE status = 'pending'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve_rule_proposal(db_path, proposal_id, reviewer="clinician"):
    """Mark a rule proposal as approved.

    Args:
        db_path: Path to the SQLite database file.
        proposal_id: The auto-incremented ID of the rule proposal.
        reviewer: Name or identifier of the reviewing clinician.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE rule_proposals SET status = 'approved', reviewed_by = ? WHERE id = ?",
            (reviewer, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()


def generate_proposals(db_path, classifier_path):
    """Apply approved synonyms and detect new combination patterns.

    This is the main function called periodically or at session end.
    First applies any approved synonym proposals to the classifier source
    file, then scans corrected exchanges for recurring symptom combinations
    and creates rule proposals for patterns that don't already have one.

    Args:
        db_path: Path to the SQLite database file.
        classifier_path: Path to risk_classifier.py on disk.

    Returns:
        A dict with keys:
        - "synonyms_applied": list of applied synonym dicts
        - "new_proposals": list of newly created rule proposal dicts
    """
    synonyms_applied = apply_approved_synonyms(db_path, classifier_path)

    patterns = detect_combination_patterns(db_path)
    new_proposals = []

    # Get existing pending/approved rule proposals to avoid duplicates
    existing_combos = set()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT proposed_rule FROM rule_proposals "
            "WHERE status IN ('pending', 'approved')"
        ).fetchall()
        for row in rows:
            try:
                rule = json.loads(row["proposed_rule"])
                existing_combos.add(tuple(sorted(rule.get("flags", []))))
            except (json.JSONDecodeError, TypeError):
                pass
    finally:
        conn.close()

    for pattern in patterns:
        combo_key = tuple(sorted(pattern["flags"]))
        if combo_key in existing_combos:
            continue

        description = " + ".join(pattern["flags"]) + " should be " + pattern["proposed_level"]
        proposed_rule = {
            "flags": pattern["flags"],
            "level": pattern["proposed_level"],
        }

        save_rule_proposal(
            db_path=db_path,
            proposal_type="combination_rule",
            description=description,
            supporting_evidence=pattern["session_ids"],
            proposed_rule=proposed_rule,
        )
        new_proposals.append({
            "description": description,
            "flags": pattern["flags"],
            "proposed_level": pattern["proposed_level"],
            "occurrences": pattern["occurrences"],
        })
        existing_combos.add(combo_key)

    return {
        "synonyms_applied": synonyms_applied,
        "new_proposals": new_proposals,
    }


def _extract_tier(risk_level_str):
    """Extract the tier name from a risk level string.

    Handles both plain tier names ("HIGH") and emoji-prefixed strings
    ("HIGH RISK").

    Args:
        risk_level_str: A risk level string in any format.

    Returns:
        One of "HIGH", "MODERATE", or "LOW".
    """
    if not risk_level_str:
        return "LOW"
    upper = risk_level_str.upper()
    if "HIGH" in upper:
        return "HIGH"
    if "MODERATE" in upper:
        return "MODERATE"
    return "LOW"


def _read_file(path):
    """Read a file and return its contents as a string.

    Args:
        path: Path to the file.

    Returns:
        The file contents as a string.
    """
    with open(str(path), "r", encoding="utf-8") as f:
        return f.read()


def _write_file(path, content):
    """Write content to a file, overwriting existing content.

    Args:
        path: Path to the file.
        content: String content to write.
    """
    with open(str(path), "w", encoding="utf-8") as f:
        f.write(content)


def _insert_into_flag_list(source, list_name, phrase):
    """Insert a new phrase into a flag list in the classifier source code.

    Finds the closing bracket of the named list and inserts the new
    phrase as the last entry before the bracket.

    Args:
        source: The full source code of risk_classifier.py as a string.
        list_name: The variable name ("HIGH_RISK_FLAGS" or "MODERATE_RISK_FLAGS").
        phrase: The phrase to insert (will be lowercased and quoted).

    Returns:
        The modified source code string.
    """
    # Find the list definition and its closing bracket
    pattern = re.compile(
        r'(' + re.escape(list_name) + r'\s*=\s*\[)(.*?)(]\s*)',
        re.DOTALL,
    )
    match = pattern.search(source)
    if not match:
        return source

    list_content = match.group(2)
    # Add the new phrase before the closing bracket
    new_entry = f'    "{phrase}",\n'
    # Ensure there's a newline before our new entry
    if list_content.rstrip().endswith(","):
        updated_content = list_content + new_entry
    else:
        stripped = list_content.rstrip()
        if stripped:
            updated_content = list_content.rstrip() + ",\n" + new_entry
        else:
            updated_content = list_content + new_entry

    return source[:match.start(2)] + updated_content + source[match.end(2):]


def _mark_proposal_applied(db_path, proposal_id):
    """Mark a synonym proposal as applied in the database.

    Args:
        db_path: Path to the SQLite database file.
        proposal_id: The auto-incremented ID of the synonym proposal.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE synonym_proposals SET status = 'applied' WHERE id = ?",
            (proposal_id,),
        )
        conn.commit()
    finally:
        conn.close()
