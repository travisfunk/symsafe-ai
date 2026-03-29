"""
ai_analyzer.py — AI-powered session analysis for the clinician review interface.

Provides functions for generating comprehensive session analyses, bulk synonym
suggestions, and response templates using Claude Haiku. All functions include
error handling and return safe fallbacks on failure.
"""

import json


def analyze_session(client, session_data, exchanges, classifier_flags):
    """Analyze a triage session and generate a comprehensive review for clinicians.

    Makes a single call to Claude Haiku with the full session context to produce
    a structured analysis including clinical summary, risk assessment, response
    quality scores, synonym suggestions, and review priority.

    Args:
        client: An initialized Anthropic client instance.
        session_data: Dict containing session metadata and intake answers.
        exchanges: List of exchange dicts from the session.
        classifier_flags: Dict with 'high' and 'moderate' flag lists.

    Returns:
        A dict with analysis results, or a minimal fallback dict on failure.
    """
    fallback = {"clinical_summary": "Analysis unavailable — AI response could not be parsed."}

    if client is None:
        return fallback

    intake = session_data.get("intake_answers") or {}
    exchange_text = ""
    for i, ex in enumerate(exchanges):
        exchange_text += f"\n--- Exchange {i + 1} ---\n"
        exchange_text += f"Patient: {ex.get('user_input', '')}\n"
        exchange_text += f"AI Response: {ex.get('assistant_response', '')}\n"
        exchange_text += f"Local risk: {ex.get('local_risk_level', 'N/A')} | Flags: {ex.get('local_risk_flags', [])}\n"
        exchange_text += f"GPT risk: {ex.get('gpt_risk_level', 'N/A')} | Flags: {ex.get('gpt_risk_flags', [])}\n"
        exchange_text += f"Merged risk: {ex.get('merged_risk_level', 'N/A')} | Care: {ex.get('care_level', 'N/A')}\n"

    high_flags = classifier_flags.get("high", [])
    moderate_flags = classifier_flags.get("moderate", [])

    prompt = f"""Analyze this triage session:

INTAKE: {json.dumps(intake)}

EXCHANGES:{exchange_text}

CURRENT CLASSIFIER FLAGS:
HIGH: {', '.join(high_flags[:20])}
MODERATE: {', '.join(moderate_flags[:15])}

Return JSON with these keys:
- clinical_summary (string, 2-3 sentences)
- risk_assessment (object: ai_risk_was_appropriate bool, explanation string, suggested_risk string HIGH/MODERATE/LOW, reasoning string)
- response_quality (array, one per exchange: exchange_index int, score string good/needs_improvement/poor, feedback string, suggested_improvement string, missed_questions array of strings)
- differential_considerations (array of strings like "URI/common cold — most consistent")
- synonym_suggestions (array: phrase string, should_map_to string, category HIGH/MODERATE/LOW, reason string, similar_phrases array)
- response_templates (array: trigger_pattern string, template string, care_level string)
- intake_observations (string)
- review_priority (string: routine/needs_attention/urgent)
- priority_reason (string)
- pattern_notes (string)"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system="You are a clinical review assistant analyzing triage sessions for a clinician. Use clinical terminology, be direct. Return ONLY valid JSON.",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, KeyError, IndexError):
        return fallback
    except Exception:
        return fallback


def generate_bulk_synonyms(client, approved_phrase, mapped_to, category):
    """Generate related phrases patients might use for an approved synonym.

    Calls Claude Haiku to suggest 10-15 variations of a known symptom phrase
    that patients might use colloquially.

    Args:
        client: An initialized Anthropic client instance.
        approved_phrase: The approved synonym phrase.
        mapped_to: The canonical flag this phrase maps to.
        category: Risk category (HIGH or MODERATE).

    Returns:
        A list of dicts with 'phrase' and 'confidence' keys, or empty list on failure.
    """
    if client is None:
        return []

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system="You are helping build a medical symptom classifier. Given an approved synonym mapping, generate related phrases patients might use. Return ONLY a JSON array of objects with phrase and confidence (0-1) keys.",
            messages=[{"role": "user", "content": f'Approved mapping: "{approved_phrase}" -> "{mapped_to}" (category: {category})\n\nGenerate 10-15 related phrases patients might use:'}],
            temperature=0.5,
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        if isinstance(result, list):
            return result
        return []
    except Exception:
        return []


def generate_response_template(client, patient_input, intake_context, ideal_response):
    """Create a reusable response template from a clinician-corrected response.

    Args:
        client: An initialized Anthropic client instance.
        patient_input: The original patient message.
        intake_context: Intake questionnaire context string.
        ideal_response: The clinician's corrected/ideal response.

    Returns:
        A dict with trigger_pattern, template_response, care_level, risk_level keys,
        or None on failure.
    """
    if client is None:
        return None

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system="You are helping build a clinical triage response library. Given a corrected response, create a reusable template. Return ONLY JSON with keys: trigger_pattern, template_response, care_level, risk_level.",
            messages=[{"role": "user", "content": f"Patient: {patient_input}\nIntake: {intake_context}\nIdeal response: {ideal_response}\n\nCreate a reusable template:"}],
            temperature=0.3,
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception:
        return None
