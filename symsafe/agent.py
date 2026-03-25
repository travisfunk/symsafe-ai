"""
agent.py — Primary GPT-4o interaction with structured JSON output.

Handles the main assistant API call, instructing GPT-4o to return a
structured JSON response containing the conversational reply, risk
assessment, follow-up questions, and care level recommendation. Includes
fallback parsing for malformed responses and code-fenced output.
"""

import json

# System instruction appended to every GPT call, requiring structured JSON output.
# Defines the exact schema and care level definitions so GPT returns actionable data.
JSON_INSTRUCTION = (
    'IMPORTANT: You must respond ONLY with valid JSON in this exact format, no other text: '
    '{"response": "your conversational reply", "risk_level": "HIGH or MODERATE or LOW", '
    '"risk_flags": ["list of concerning symptoms identified"], '
    '"follow_up_questions": ["1-2 relevant follow-up questions if appropriate, empty list if none needed"], '
    '"care_level": "emergency | urgent_care | primary_care | telehealth | self_care"} '
    'care_level definitions: '
    '"emergency" — Call 911 or go to ER immediately (life-threatening symptoms). '
    '"urgent_care" — Visit urgent care or walk-in clinic today (needs attention but not life-threatening). '
    '"primary_care" — Schedule an appointment with your doctor this week. '
    '"telehealth" — A virtual visit could address this. '
    '"self_care" — Monitor at home, seek care if symptoms worsen.'
)


def _parse_response(raw_text):
    """Parse structured JSON from GPT output, with code fence stripping and fallback."""
    text = raw_text.strip()
    # GPT sometimes wraps JSON in markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Fallback: treat as plain text with safe defaults
        return {
            "response": raw_text,
            "risk_level": "LOW",
            "risk_flags": [],
            "follow_up_questions": [],
            "care_level": "self_care"
        }


def get_assistant_response(client, messages):
    """Send messages to GPT-4o and return a structured response dict.

    Appends a temporary JSON instruction to the message list (without
    modifying the caller's list) to enforce structured output. Parses
    the response and falls back to safe defaults if JSON parsing fails.

    Args:
        client: An initialized OpenAI client instance.
        messages: The conversation message history (list of role/content dicts).

    Returns:
        A dict with keys: response, risk_level, risk_flags,
        follow_up_questions, care_level. Returns None on API failure.
    """
    json_hint = {"role": "system", "content": JSON_INSTRUCTION}
    messages_with_hint = messages + [json_hint]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages_with_hint,
            temperature=0.7
        )
        raw_text = response.choices[0].message.content.strip()
        return _parse_response(raw_text)
    except Exception:
        return None
