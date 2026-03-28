"""
report.py — Patient Preparation Document generator.

Produces a standalone HTML report that patients can print and bring to
their doctor. Includes intake data, symptom timeline, risk assessment,
conversation summary, follow-up questions, and care guidance. The HTML
is self-contained with embedded styles and print-friendly CSS.
"""

from pathlib import Path
from datetime import datetime
from symsafe.care_router import get_care_guidance

# Maps intake step IDs to display labels for the report table.
INTAKE_LABEL_MAP = {
    "concern": "Main concern",
    "location": "Location",
    "onset": "Onset",
    "severity": "Severity",
    "trajectory": "Trajectory",
    "medications": "Medications",
    "conditions": "Chronic conditions",
}

# CSS border/badge colors for each risk tier: (border_color, badge_background).
RISK_COLORS = {
    "HIGH": ("#c0392b", "#e74c3c"),
    "MODERATE": ("#e67e22", "#f39c12"),
    "LOW": ("#27ae60", "#2ecc71"),
}


def _escape(text):
    """Escape HTML special characters to prevent injection."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_timestamp(timestamp):
    """Convert a YYYYMMDD_HHMMSS timestamp to a human-readable date string."""
    try:
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except (ValueError, TypeError):
        return timestamp


def generate_report(
    timestamp,
    intake_answers,
    session_symptoms,
    highest_risk,
    highest_care_level,
    message_count,
    conversation_log,
    provider_questions=None,
    follow_up_questions=None,
):
    """Generate a standalone HTML Patient Preparation Document.

    Assembles all session data into a printable, professional report
    designed for patients to share with their healthcare provider.

    Args:
        timestamp: Session timestamp string (YYYYMMDD_HHMMSS format).
        intake_answers: Dict of intake questionnaire answers, or None.
        session_symptoms: List of symptom strings identified during the session.
        highest_risk: The highest risk tier reached ("HIGH", "MODERATE", or "LOW").
        highest_care_level: The highest care level reached (e.g., "emergency").
        message_count: Total number of patient messages in the session.
        conversation_log: List of dicts with keys: user, assistant, risk,
                          care_level, risk_flags.
        provider_questions: List of questions the patient should ask their
                            doctor at their appointment.
        follow_up_questions: Deprecated. Use provider_questions instead.

    Returns:
        A complete HTML document as a string.
    """
    # Support both parameter names for backwards compatibility
    if provider_questions is None and follow_up_questions is not None:
        provider_questions = follow_up_questions
    risk_color, risk_bg = RISK_COLORS.get(highest_risk, RISK_COLORS["LOW"])
    care_guidance = get_care_guidance(highest_care_level)
    formatted_date = _format_timestamp(timestamp)

    # Build intake section
    intake_html = ""
    if intake_answers:
        rows = ""
        for step_id, label in INTAKE_LABEL_MAP.items():
            if step_id in intake_answers:
                val = _escape(intake_answers[step_id])
                if step_id == "severity":
                    val = f"{val}/10"
                rows += f"<tr><td><strong>{_escape(label)}</strong></td><td>{val}</td></tr>\n"
        intake_html = f"""
    <section>
      <h2>Patient Intake</h2>
      <table class="intake-table">
        {rows}
      </table>
    </section>"""

    # Build symptoms section
    unique_symptoms = list(dict.fromkeys(session_symptoms))
    symptoms_items = "".join(f"<li>{_escape(s)}</li>\n" for s in unique_symptoms)
    symptoms_html = f"""
    <section>
      <h2>Presenting Symptoms</h2>
      <ul>{symptoms_items}</ul>
    </section>""" if unique_symptoms else ""

    # Build risk assessment section
    risk_html = f"""
    <section>
      <h2>Risk Assessment</h2>
      <div class="risk-badge" style="background-color:{risk_bg};color:#fff;padding:8px 16px;border-radius:4px;display:inline-block;font-weight:bold;">
        {_escape(highest_risk)} RISK
      </div>
      <p><strong>Care recommendation:</strong> {_escape(care_guidance['where'])}</p>
      <p><strong>Why:</strong> {_escape(care_guidance['why'])}</p>
    </section>"""

    # Build conversation summary (condensed: patient message + AI assessment)
    convo_items = ""
    for entry in conversation_log:
        user_msg = _escape(entry.get("user", ""))
        risk = _escape(entry.get("risk", ""))
        flags = entry.get("risk_flags", [])
        care = entry.get("care_level", "")
        assessment_parts = []
        if care and care != "self_care":
            assessment_parts.append(f"Recommended {_escape(care).replace('_', ' ')}")
        if flags:
            assessment_parts.append(f"Identified: {', '.join(_escape(f) for f in flags)}")
        assessment = ". ".join(assessment_parts) if assessment_parts else "No clinical concerns identified."
        convo_items += f"""
      <div class="convo-entry">
        <p class="patient-msg"><strong>Patient:</strong> {user_msg}</p>
        <p class="ai-assessment"><strong>AI Assessment:</strong> {assessment}</p>
      </div>"""

    convo_html = f"""
    <section>
      <h2>Conversation Summary</h2>
      <p>Messages exchanged: {message_count}</p>
      {convo_items}
    </section>""" if conversation_log else ""

    # Build provider questions section with answer lines for printing
    followup_html = ""
    if provider_questions:
        question_blocks = ""
        for q in provider_questions:
            question_blocks += f"""
      <div style="margin-bottom:20px">
        <p style="font-weight:600;margin-bottom:4px">{_escape(q)}</p>
        <p style="font-size:12px;color:#888;margin-bottom:2px">Doctor's answer:</p>
        <div style="border-bottom:1px solid #999;min-height:24px;margin-bottom:8px"></div>
        <div style="border-bottom:1px solid #999;min-height:24px"></div>
      </div>"""
        followup_html = f"""
    <section>
      <h2>Questions to Ask Your Provider</h2>
      <p>Bring this report to your appointment. Use the lines below to write down your doctor's answers.</p>
      {question_blocks}
    </section>"""

    # Build immediate action section
    action_html = f"""
    <section>
      <h2>What To Do Right Now</h2>
      <p>{_escape(care_guidance['right_now'])}</p>
    </section>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SymSafe Triage Report</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 800px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      text-align: center;
      border-bottom: 3px solid {risk_color};
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    header h1 {{ font-size: 24px; color: #2c3e50; }}
    header p {{ color: #7f8c8d; font-size: 14px; }}
    section {{
      margin-bottom: 28px;
      padding-bottom: 16px;
      border-bottom: 1px solid #ecf0f1;
    }}
    h2 {{
      font-size: 18px;
      color: #2c3e50;
      margin-bottom: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .intake-table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .intake-table td {{
      padding: 6px 12px;
      border-bottom: 1px solid #ecf0f1;
    }}
    .intake-table td:first-child {{ width: 40%; color: #555; }}
    ul {{ padding-left: 20px; }}
    li {{ margin-bottom: 4px; }}
    .risk-badge {{ margin-bottom: 12px; }}
    .convo-entry {{
      margin-bottom: 12px;
      padding: 8px 12px;
      background: #f9f9f9;
      border-left: 3px solid #bdc3c7;
      border-radius: 2px;
    }}
    .patient-msg {{ margin-bottom: 4px; }}
    .ai-assessment {{ color: #555; font-size: 14px; }}
    .disclaimer {{
      margin-top: 32px;
      padding: 16px;
      background: #fdf2e9;
      border: 1px solid #e67e22;
      border-radius: 4px;
      font-size: 13px;
      color: #7f6c5b;
    }}
    @media print {{
      body {{ padding: 0; }}
      .risk-badge {{ background-color: transparent !important; color: {risk_color} !important; border: 2px solid {risk_color}; }}
      .convo-entry {{ background: transparent; border-left: 2px solid #999; }}
      .disclaimer {{ background: transparent; border: 1px solid #999; }}
      section {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>SymSafe Triage Report</h1>
    <p>Generated: {_escape(formatted_date)}</p>
  </header>
{intake_html}
{symptoms_html}
{risk_html}
{convo_html}
{followup_html}
{action_html}
  <div class="disclaimer">
    <strong>IMPORTANT:</strong> This report was generated by SymSafe, an AI triage assistant.
    It is <strong>not a medical diagnosis</strong>. It is designed to help you communicate
    with your healthcare provider. Always follow your provider's advice
    over any information in this report.
  </div>
</body>
</html>"""

    return html


def save_report(html_content, output_dir, timestamp):
    """Save an HTML report to the reports directory.

    Args:
        html_content: The complete HTML string to write.
        output_dir: Directory path for output (created if it doesn't exist).
        timestamp: Session timestamp used in the filename.

    Returns:
        Path: The file path of the saved report.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"symsafe_report_{timestamp}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return file_path
