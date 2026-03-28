"""
agent.py — Primary Claude interaction with structured JSON output.

Handles the main assistant API call, instructing Claude to return a
structured JSON response containing the conversational reply, risk
assessment, follow-up questions, and care level recommendation. Includes
fallback parsing for malformed responses and code-fenced output.
"""

import json

# System instruction appended to every API call, requiring structured JSON output.
# Defines the exact schema and care level definitions so Claude returns actionable data.
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
    """Parse structured JSON from model output, with code fence stripping and fallback."""
    text = raw_text.strip()
    # Model sometimes wraps JSON in markdown code fences
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
    """Send messages to Claude and return a structured response dict.

    Extracts system messages into the system parameter and user/assistant
    messages into the messages list. Appends a JSON instruction to enforce
    structured output. Parses the response and falls back to safe defaults
    if JSON parsing fails.

    Args:
        client: An initialized Anthropic client instance.
        messages: The conversation message history (list of role/content dicts).

    Returns:
        A dict with keys: response, risk_level, risk_flags,
        follow_up_questions, care_level. Returns None on API failure.
    """
    messages_with_hint = messages + [{"role": "system", "content": JSON_INSTRUCTION}]

    # Separate system messages from user/assistant messages for the Anthropic API
    system_parts = [m["content"] for m in messages_with_hint if m["role"] == "system"]
    system_prompt = "\n\n".join(system_parts)
    conversation = [m for m in messages_with_hint if m["role"] in ("user", "assistant")]

    # Ensure conversation is non-empty and starts with a user message
    if not conversation:
        conversation = [{"role": "user", "content": "Hello"}]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=conversation,
            temperature=0.7
        )
        raw_text = response.content[0].text.strip()
        return _parse_response(raw_text)
    except Exception:
        return None
