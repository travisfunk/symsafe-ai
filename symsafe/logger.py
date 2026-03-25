"""
logger.py — Markdown session logging for auditability.

Handles all file-based logging: creating timestamped log files, recording
intake data, logging each conversation interaction with full metadata,
and writing session summaries. Every session produces a complete audit
trail in the logs/ directory.
"""

from symsafe.config import BASE_DIR
from symsafe.care_router import get_care_guidance

# Maps intake step IDs to display labels for log formatting.
INTAKE_LABEL_MAP = {
    "concern": "Main concern",
    "location": "Location",
    "onset": "Onset",
    "severity": "Severity",
    "trajectory": "Trajectory",
    "medications": "Medications",
    "conditions": "Chronic conditions",
}


def create_log_file(log_dir, timestamp):
    """Create a new timestamped markdown log file with a header.

    Args:
        log_dir: Path to the logs directory (created if needed).
        timestamp: Session timestamp string for the filename.

    Returns:
        Path: The file path of the created log file.
    """
    log_dir.mkdir(exist_ok=True)
    log_filename = log_dir / f"convo_{timestamp}.md"
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write(f"# SymSafe Interaction Log – {timestamp}\n\n")
    return log_filename


def log_intake(log_filename, answers):
    """Append intake questionnaire answers to the log file.

    Args:
        log_filename: Path to the active log file.
        answers: Dict of intake answers keyed by step ID. May be empty.
    """
    with open(log_filename, "a", encoding="utf-8") as log_file:
        log_file.write("## Patient Intake\n\n")
        if answers:
            for step_id, label in INTAKE_LABEL_MAP.items():
                if step_id in answers:
                    value = answers[step_id]
                    if step_id == "severity":
                        log_file.write(f"- **{label}:** {value}/10\n")
                    else:
                        log_file.write(f"- **{label}:** {value}\n")
        else:
            log_file.write("No intake data collected.\n")
        log_file.write("\n---\n\n")


def log_interaction(log_filename, user_input, risk_level, risk_flags, reply, evaluation, tree_matches, follow_up_questions=None, care_level=None):
    """Append a single conversation interaction to the log file.

    Records the full context of one exchange: patient input, risk assessment,
    care routing, symptom tree matches, assistant response, follow-up
    questions, and evaluation results.

    Args:
        log_filename: Path to the active log file.
        user_input: The patient's message text.
        risk_level: The merged risk level string (e.g., "HIGH RISK").
        risk_flags: List of matched risk flag strings.
        reply: The assistant's response text.
        evaluation: Evaluation text, or None if skipped.
        tree_matches: List of (symptom_key, guidance) tuples.
        follow_up_questions: Optional list of follow-up question strings.
        care_level: Optional care level string (e.g., "emergency").
    """
    with open(log_filename, "a", encoding="utf-8") as log_file:
        log_file.write(f"**User:** {user_input}\n")
        risk_log = risk_level
        if risk_flags:
            risk_log = f"{risk_level} — matched: {', '.join(risk_flags)}"
        log_file.write(f"**Risk Level:** {risk_log}\n")
        if care_level and care_level != "self_care":
            log_file.write(f"**Care Routing:** {care_level}\n")
        if tree_matches:
            matched_names = [m[0] for m in tree_matches]
            log_file.write(f"**Symptom Tree Matches:** {', '.join(matched_names)}\n")
        log_file.write(f"**Assistant:** {reply}\n\n")
        if follow_up_questions:
            log_file.write("**Follow-up Questions:**\n")
            for q in follow_up_questions:
                log_file.write(f"- {q}\n")
            log_file.write("\n")
        if evaluation is None:
            log_file.write("**AI Self-Evaluation:** Skipped (non-clinical message)\n\n")
        else:
            log_file.write("**AI Self-Evaluation:**\n")
            log_file.write(f"{evaluation}\n\n")
        log_file.write("---\n")


def log_session_summary(log_filename, symptoms, highest_risk, message_count, highest_care_level=None):
    """Append the session summary to the log file.

    Args:
        log_filename: Path to the active log file.
        symptoms: Deduplicated list of symptom strings from the session.
        highest_risk: The highest risk tier reached ("HIGH", "MODERATE", "LOW").
        message_count: Total number of patient messages exchanged.
        highest_care_level: Optional highest care level from the session.
    """
    with open(log_filename, "a", encoding="utf-8") as log_file:
        log_file.write("\n---\n\n")
        log_file.write("## Session Summary\n\n")
        if symptoms:
            log_file.write(f"**Symptoms discussed:** {', '.join(symptoms)}\n")
        else:
            log_file.write("**Symptoms discussed:** None\n")
        log_file.write(f"**Highest risk level:** {highest_risk}\n")
        log_file.write(f"**Messages exchanged:** {message_count}\n")
        if highest_risk == "HIGH":
            log_file.write("**Recommended action:** Seek immediate medical evaluation\n")
        elif highest_risk == "MODERATE":
            log_file.write("**Recommended action:** Schedule an appointment with your healthcare provider\n")
        else:
            log_file.write("**Recommended action:** No urgent action needed — see a provider if symptoms develop\n")
        if highest_care_level and highest_care_level != "self_care":
            guidance = get_care_guidance(highest_care_level)
            log_file.write(f"**Recommended care:** {guidance['where']}\n")
