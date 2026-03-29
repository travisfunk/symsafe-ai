"""
app.py — Flask web application for the SymSafe patient and clinician UI.

Provides a web interface to the same backend modules used by the CLI.
Routes handle intake submission, chat exchanges with dual-layer risk
assessment, session end with report generation, static report serving,
and clinician review workflows. Includes input sanitization, rate limiting,
authentication for clinician routes, and security headers.
"""

import datetime
import functools
import logging
import os
import re
import urllib.parse

from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for

from symsafe.config import BASE_DIR, DB_PATH, get_client, load_base_prompt
from symsafe.risk_classifier import classify_risk, load_combination_rules_from_db, HIGH_RISK_FLAGS, MODERATE_RISK_FLAGS
from symsafe.symptom_tree import match_symptom_tree, load_symptom_tree
from symsafe.evaluator import run_auto_evaluation
from symsafe.agent import get_assistant_response
from symsafe.logger import create_log_file, log_interaction, log_session_summary, log_intake
from symsafe.care_router import get_care_guidance, merge_care_level, CARE_LEVEL_HIERARCHY
from symsafe.intake import format_intake_context
from symsafe.report import generate_report, save_report
from symsafe.store import (
    init_db, save_session, update_session, save_exchange, get_all_sessions,
    get_session, get_exchanges, update_session_status, update_exchange_review,
    get_session_stats, get_synonym_proposals_for_session,
    get_all_synonym_proposals, get_all_rule_proposals, count_similar_exchanges,
    save_analysis, get_analysis,
)
from symsafe.ai_analyzer import analyze_session, generate_bulk_synonyms
from symsafe.feedback import (
    detect_classifier_gap, find_nearest_flag, save_synonym_proposal,
    generate_proposals, get_pending_proposals, approve_synonym,
    reject_proposal, approve_rule_proposal, get_pending_rule_proposals,
    apply_approved_synonyms, save_rule_proposal,
)
from symsafe.risk_classifier import apply_combination_rule, COMBINATION_RULES

logger = logging.getLogger(__name__)

RISK_HIERARCHY = {"LOW": 0, "MODERATE": 1, "HIGH": 2}

CARE_SEARCH_TERMS = {
    "emergency": "emergency+room",
    "urgent_care": "urgent+care",
    "primary_care": "primary+care+doctor",
    "telehealth": "telehealth",
}

VALID_RISK_LEVELS = {"HIGH", "MODERATE", "LOW"}
VALID_CARE_LEVELS = {"emergency", "urgent_care", "primary_care", "telehealth", "self_care"}
VALID_REVIEW_ACTIONS = {"accepted", "corrected", "rejected"}
VALID_PROPOSAL_ACTIONS = {"approve", "reject"}
VALID_SESSION_STATUSES = {"reviewed", "flagged"}

MAX_SESSION_MESSAGES = 30

_sessions = {}

_RE_SESSION_ID = re.compile(r'^[a-zA-Z0-9_]+$')
_RE_HTML_TAG = re.compile(r'<[^>]+>')
_RE_ZIP = re.compile(r'^\d{5}$')


def sanitize_input(text, max_length=1000):
    """Strip HTML tags and enforce maximum length on user input.

    Args:
        text: The raw input string.
        max_length: Maximum allowed character count.

    Returns:
        The sanitized string, or None if input was not a string.
    """
    if not isinstance(text, str):
        return None
    text = _RE_HTML_TAG.sub('', text)
    return text[:max_length]


def _validate_session_id(session_id):
    """Return True if session_id matches the expected alphanumeric/underscore pattern."""
    if not session_id or not isinstance(session_id, str):
        return False
    return bool(_RE_SESSION_ID.match(session_id))


def build_maps_link(care_level, zip_code=None):
    """Build a Google Maps search URL for the given care level and location.

    Args:
        care_level: One of the care level strings (e.g. "emergency").
        zip_code: Optional zip code string for location targeting.

    Returns:
        A Google Maps search URL string, or None for self_care/telehealth.
    """
    search_term = CARE_SEARCH_TERMS.get(care_level)
    if not search_term:
        return None
    location = urllib.parse.quote_plus(zip_code) if zip_code else "me"
    return f"https://www.google.com/maps/search/{search_term}+near+{location}"


def _merge_risk(local_level, gpt_level_str):
    """Return the higher of local and GPT risk levels as an emoji-prefixed string."""
    local_tier = "LOW"
    if "HIGH" in local_level.upper():
        local_tier = "HIGH"
    elif "MODERATE" in local_level.upper():
        local_tier = "MODERATE"

    gpt_tier = gpt_level_str.upper() if gpt_level_str else "LOW"
    if gpt_tier not in RISK_HIERARCHY:
        gpt_tier = "LOW"

    if RISK_HIERARCHY.get(gpt_tier, 0) > RISK_HIERARCHY.get(local_tier, 0):
        winner = gpt_tier
    else:
        winner = local_tier

    if winner == "HIGH":
        return "\U0001f534 HIGH RISK"
    elif winner == "MODERATE":
        return "\U0001f7e1 MODERATE RISK"
    return "\U0001f7e2 LOW RISK"


def _get_banner(merged_risk_level):
    """Return a banner type string based on merged risk level."""
    upper = merged_risk_level.upper()
    if "HIGH" in upper:
        return "high"
    if "MODERATE" in upper:
        return "moderate"
    return "none"


def determine_patient_banner(local_risk_level, gpt_risk_level, all_flags, care_level):
    """Determine the patient-facing banner and care level.

    Decouples the patient display from the internal risk classification.
    The internal classification stays aggressive for clinician review, but
    the patient sees proportionate, calm guidance.

    Args:
        local_risk_level: Risk level string from the local keyword classifier.
        gpt_risk_level: Risk level string from GPT's assessment.
        all_flags: Combined list of risk flag strings from both classifiers.
        care_level: The internal merged care level string.

    Returns:
        A tuple of (patient_banner, patient_care_level) where patient_banner
        is one of "emergency", "attention", "moderate", "none" and
        patient_care_level is the care level to display to the patient.
    """
    local_tier = "LOW"
    if "HIGH" in local_risk_level.upper():
        local_tier = "HIGH"
    elif "MODERATE" in local_risk_level.upper():
        local_tier = "MODERATE"

    gpt_tier = gpt_risk_level.upper() if gpt_risk_level else "LOW"

    combo_fired = any("combination:" in f for f in all_flags)

    if local_tier == "HIGH" and (gpt_tier == "HIGH" or combo_fired):
        patient_banner = "emergency"
    elif local_tier == "HIGH" and gpt_tier in ("MODERATE", "LOW"):
        patient_banner = "attention"
    elif "MODERATE" in _merge_risk(local_risk_level, gpt_risk_level).upper():
        patient_banner = "moderate"
    else:
        patient_banner = "none"

    patient_care_level = care_level
    if patient_banner == "attention" and care_level == "emergency":
        patient_care_level = "urgent_care"

    return patient_banner, patient_care_level


def _get_or_create_session(session_id, base_prompt, symptom_tree):
    """Get existing session state or create a new one."""
    if session_id not in _sessions:
        log_dir = BASE_DIR / "logs"
        log_filename = create_log_file(log_dir, session_id)

        _sessions[session_id] = {
            "messages": [{"role": "system", "content": base_prompt}],
            "session_symptoms": [],
            "session_highest_risk": "LOW",
            "session_highest_care_level": "self_care",
            "session_message_count": 0,
            "exchange_index": 0,
            "conversation_log": [],
            "session_follow_ups": [],
            "session_provider_questions": [],
            "messages_since_escalation": 0,
            "last_escalation_care_level": None,
            "intake_answers": None,
            "zip_code": None,
            "log_filename": log_filename,
            "symptom_tree": symptom_tree,
        }
        save_session(
            session_id=session_id,
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=0,
            session_symptoms=[],
            zip_code=None,
        )
    return _sessions[session_id]


def create_app(test_config=None):
    """Create and configure the Flask application.

    Args:
        test_config: Optional dict of configuration overrides for testing.

    Returns:
        A configured Flask app instance.
    """
    template_dir = str(BASE_DIR / "symsafe" / "web" / "templates")
    app = Flask(__name__, template_folder=template_dir)

    # Secure session configuration
    secret = os.environ.get("FLASK_SECRET_KEY")
    if not secret:
        secret = "symsafe-dev-key-change-in-production"
        if not (test_config and test_config.get("TESTING")):
            logger.warning("FLASK_SECRET_KEY not set. Using insecure default. Set FLASK_SECRET_KEY in production.")
    app.secret_key = secret

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    if test_config:
        app.config.update(test_config)

    # Load resources once at startup
    init_db()
    stats = get_session_stats()
    if stats.get("total_sessions", 0) == 0:
        try:
            from scripts.seed_demo_data import seed_all
            seed_all()
            logger.info("Seeded demo data into empty database.")
        except Exception as e:
            logger.warning(f"Could not seed demo data: {e}")
    load_combination_rules_from_db(DB_PATH)
    classifier_path = BASE_DIR / "symsafe" / "risk_classifier.py"
    generate_proposals(DB_PATH, classifier_path)

    try:
        base_prompt = load_base_prompt()
    except FileNotFoundError:
        base_prompt = "You are a helpful healthcare triage assistant."

    symptom_tree = load_symptom_tree()

    # API key validation
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_api_key = bool(api_key and api_key != "your_api_key_here")
    if not has_api_key:
        logger.warning("ANTHROPIC_API_KEY not set or invalid. Chat functionality will be unavailable.")

    client = get_client() if has_api_key else None

    review_password = os.environ.get("REVIEW_PASSWORD", "symsafe-review")

    def require_review_auth(f):
        """Decorator that requires clinician authentication for review routes."""
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if app.config.get("TESTING"):
                return f(*args, **kwargs)
            if not session.get("review_authenticated"):
                return redirect(url_for("review_login"))
            return f(*args, **kwargs)
        return decorated

    # Security headers on all responses
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # --- Patient routes ---

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/intake", methods=["POST"])
    def intake():
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            session_id = data.get("session_id")
            if session_id and not _validate_session_id(session_id):
                return jsonify({"error": "Invalid session ID format"}), 400
            if not session_id:
                session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            state = _get_or_create_session(session_id, base_prompt, symptom_tree)

            answers = data.get("answers", {})
            if not isinstance(answers, dict):
                answers = {}

            # Sanitize intake fields
            sanitized = {}
            for key in ("concern", "location", "onset", "trajectory"):
                if key in answers and isinstance(answers[key], str):
                    sanitized[key] = sanitize_input(answers[key], max_length=100)

            if "severity" in answers:
                sev = str(answers["severity"]).strip()
                try:
                    sev_int = int(sev)
                    if 1 <= sev_int <= 10:
                        sanitized["severity"] = str(sev_int)
                except (ValueError, TypeError):
                    pass

            for key in ("medications", "conditions"):
                if key in answers and isinstance(answers[key], str):
                    sanitized[key] = sanitize_input(answers[key], max_length=500)

            zip_code = data.get("zip_code")
            if zip_code and isinstance(zip_code, str):
                zip_code = zip_code.strip()
                if not _RE_ZIP.match(zip_code):
                    zip_code = None

            state["intake_answers"] = sanitized
            state["zip_code"] = zip_code

            if sanitized:
                context = format_intake_context(sanitized)
                if context:
                    state["messages"].append({"role": "system", "content": context})
                if "concern" in sanitized:
                    state["session_symptoms"].append(sanitized["concern"].lower())
                if "location" in sanitized and sanitized["location"].lower() not in ("not applicable", "all over"):
                    state["session_symptoms"].append(sanitized["location"].lower())
                log_intake(state["log_filename"], sanitized)
            else:
                log_intake(state["log_filename"], {})

            session["session_id"] = session_id
            return jsonify({"status": "ok", "session_id": session_id})
        except Exception:
            logger.exception("Error in /api/intake")
            return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

    @app.route("/api/chat", methods=["POST"])
    def chat():
        try:
            if not has_api_key or client is None:
                return jsonify({"error": "Chat is temporarily unavailable. Please try again later."}), 503

            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            raw_message = data.get("message")
            if not isinstance(raw_message, str):
                return jsonify({"error": "Message is required"}), 400

            raw_message = raw_message.strip()
            if len(raw_message) > 1000:
                return jsonify({"error": "Message too long. Please keep under 1000 characters."}), 400

            user_input = sanitize_input(raw_message, max_length=1000)
            if not user_input:
                return jsonify({"error": "Message is required"}), 400

            session_id = data.get("session_id") or session.get("session_id")
            if session_id and not _validate_session_id(session_id):
                return jsonify({"error": "Invalid session ID format"}), 400
            if not session_id:
                session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                session["session_id"] = session_id

            state = _get_or_create_session(session_id, base_prompt, symptom_tree)

            # Rate limiting: max messages per session
            if state["session_message_count"] >= MAX_SESSION_MESSAGES:
                return jsonify({"error": "Session message limit reached. Please end this session and start a new one."}), 429

            st = state["symptom_tree"]

            # Re-escalation check
            re_escalation = None
            if (state["last_escalation_care_level"] in ("emergency", "urgent_care")
                    and state["messages_since_escalation"] >= 3):
                care_word = "emergency care" if state["last_escalation_care_level"] == "emergency" else "urgent care"
                re_escalation = f"I recommended {care_word} earlier. If you haven't sought care yet, please prioritize that."
                state["messages_since_escalation"] = 0

            state["messages"].append({"role": "user", "content": user_input})
            local_risk_level, local_risk_flags = classify_risk(user_input)

            tree_matches = match_symptom_tree(user_input, st)
            hint_message = None
            if tree_matches:
                guidance = "; ".join(f"{k}: {v}" for k, v in tree_matches)
                hint_message = {"role": "system", "content": f"Clinical reference for reported symptoms: {guidance}. Use this to inform your response, but still reply conversationally."}
                state["messages"].append(hint_message)

            if len(state["messages"]) > 21:
                state["messages"] = [state["messages"][0]] + state["messages"][-20:]

            result = get_assistant_response(client, state["messages"])

            if hint_message and hint_message in state["messages"]:
                state["messages"].remove(hint_message)

            if result is None:
                state["messages"].pop()
                return jsonify({"error": "Could not process request. Please try again."}), 500

            reply = result["response"]
            gpt_risk_level = result.get("risk_level", "LOW")
            gpt_risk_flags = result.get("risk_flags", [])
            follow_up_questions = result.get("follow_up_questions", [])
            provider_questions = result.get("provider_questions", [])
            gpt_care_level = result.get("care_level", "self_care")

            merged_risk_level = _merge_risk(local_risk_level, gpt_risk_level)
            all_flags = list(dict.fromkeys(local_risk_flags + gpt_risk_flags))
            care_level = merge_care_level(merged_risk_level, gpt_care_level)

            state["messages"].append({"role": "assistant", "content": reply})

            state["session_message_count"] += 1
            for flag in all_flags:
                state["session_symptoms"].append(flag)
            if tree_matches:
                for m in tree_matches:
                    state["session_symptoms"].append(m[0])

            merged_tier = "LOW"
            if "HIGH" in merged_risk_level.upper():
                merged_tier = "HIGH"
            elif "MODERATE" in merged_risk_level.upper():
                merged_tier = "MODERATE"
            if RISK_HIERARCHY.get(merged_tier, 0) > RISK_HIERARCHY.get(state["session_highest_risk"], 0):
                state["session_highest_risk"] = merged_tier

            if CARE_LEVEL_HIERARCHY.get(care_level, 0) > CARE_LEVEL_HIERARCHY.get(state["session_highest_care_level"], 0):
                state["session_highest_care_level"] = care_level

            if care_level in ("emergency", "urgent_care"):
                state["last_escalation_care_level"] = care_level
                state["messages_since_escalation"] = 0
            elif "LOW" in merged_risk_level.upper() and not tree_matches:
                state["last_escalation_care_level"] = None
                state["messages_since_escalation"] = 0
            else:
                if state["last_escalation_care_level"]:
                    state["messages_since_escalation"] += 1

            state["conversation_log"].append({
                "user": user_input,
                "assistant": reply,
                "risk": merged_risk_level,
                "care_level": care_level,
                "risk_flags": all_flags,
            })
            if follow_up_questions:
                state["session_follow_ups"].extend(follow_up_questions)
            if provider_questions:
                state["session_provider_questions"].extend(provider_questions)

            is_clinical = "HIGH" in merged_risk_level.upper() or "MODERATE" in merged_risk_level.upper() or len(tree_matches) > 0
            if is_clinical:
                evaluation = run_auto_evaluation(client, user_input, reply, False)
            else:
                evaluation = None

            log_interaction(state["log_filename"], user_input, merged_risk_level, all_flags, reply, evaluation, tree_matches, follow_up_questions, care_level)

            tree_match_keys = [m[0] for m in tree_matches] if tree_matches else []
            save_exchange(
                session_id=session_id,
                exchange_index=state["exchange_index"],
                user_input=user_input,
                assistant_response=reply,
                local_risk_level=local_risk_level,
                local_risk_flags=local_risk_flags,
                gpt_risk_level=gpt_risk_level,
                gpt_risk_flags=gpt_risk_flags,
                merged_risk_level=merged_risk_level,
                care_level=care_level,
                follow_up_questions=follow_up_questions,
                evaluation=evaluation,
                tree_matches=tree_match_keys,
            )
            state["exchange_index"] += 1

            gap = detect_classifier_gap(user_input, local_risk_level, local_risk_flags, gpt_risk_level, gpt_risk_flags)
            if gap:
                all_flags_list = HIGH_RISK_FLAGS + MODERATE_RISK_FLAGS
                nearest = find_nearest_flag(user_input, all_flags_list)
                save_synonym_proposal(
                    db_path=None,
                    patient_phrase=gap["patient_phrase"],
                    gpt_risk_level=gap["gpt_risk_level"],
                    local_risk_level=gap["local_risk_level"],
                    proposed_category=gap["gpt_risk_level"],
                    proposed_synonym_for=nearest,
                    session_id=session_id,
                )

            patient_banner, patient_care_level = determine_patient_banner(
                local_risk_level, gpt_risk_level, all_flags, care_level)

            care_guidance = None
            maps_link = None
            if patient_care_level and patient_care_level != "self_care":
                care_guidance = get_care_guidance(patient_care_level)
                maps_link = build_maps_link(patient_care_level, state.get("zip_code"))

            response_data = {
                "response": reply,
                "risk_level": merged_risk_level,
                "care_level": patient_care_level,
                "care_guidance": care_guidance,
                "follow_up_questions": follow_up_questions,
                "maps_link": maps_link,
                "banner": patient_banner,
                "internal_risk": merged_risk_level,
            }
            if re_escalation:
                response_data["re_escalation"] = re_escalation

            return jsonify(response_data)
        except Exception:
            logger.exception("Error in /api/chat")
            return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

    @app.route("/api/end-session", methods=["POST"])
    def end_session():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get("session_id") or session.get("session_id")

            if session_id and not _validate_session_id(session_id):
                return jsonify({"error": "Invalid session ID format"}), 400

            if not session_id or session_id not in _sessions:
                return jsonify({
                    "summary": {
                        "session_symptoms": [],
                        "highest_risk": "LOW",
                        "message_count": 0,
                        "highest_care_level": "self_care",
                    },
                    "report_url": None,
                })

            state = _sessions[session_id]

            log_session_summary(
                state["log_filename"],
                list(dict.fromkeys(state["session_symptoms"])),
                state["session_highest_risk"],
                state["session_message_count"],
                state["session_highest_care_level"],
            )

            update_session(
                session_id=session_id,
                highest_risk=state["session_highest_risk"],
                highest_care_level=state["session_highest_care_level"],
                message_count=state["session_message_count"],
                session_symptoms=list(dict.fromkeys(state["session_symptoms"])),
                zip_code=state.get("zip_code"),
            )

            generate_proposals(DB_PATH, classifier_path)

            report_url = None
            if state["session_message_count"] > 0:
                provider_qs = list(dict.fromkeys(state["session_provider_questions"]))
                if not provider_qs:
                    provider_qs = [
                        "What do you think is causing these symptoms?",
                        "Are there any tests I should have done?",
                        "What should I watch for that would mean I need to come back?",
                    ]
                report_html = generate_report(
                    timestamp=session_id,
                    intake_answers=state["intake_answers"],
                    session_symptoms=state["session_symptoms"],
                    highest_risk=state["session_highest_risk"],
                    highest_care_level=state["session_highest_care_level"],
                    message_count=state["session_message_count"],
                    conversation_log=state["conversation_log"],
                    provider_questions=provider_qs,
                )
                reports_dir = BASE_DIR / "reports"
                save_report(report_html, reports_dir, session_id)
                report_url = f"/reports/symsafe_report_{session_id}.html"

            summary = {
                "session_symptoms": list(dict.fromkeys(state["session_symptoms"])),
                "highest_risk": state["session_highest_risk"],
                "message_count": state["session_message_count"],
                "highest_care_level": state["session_highest_care_level"],
            }

            del _sessions[session_id]
            session.pop("session_id", None)

            return jsonify({"summary": summary, "report_url": report_url})
        except Exception:
            logger.exception("Error in /api/end-session")
            return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

    @app.route("/reports/<filename>")
    def serve_report(filename):
        reports_dir = str(BASE_DIR / "reports")
        return send_from_directory(reports_dir, filename)

    # --- Clinician authentication ---

    @app.route("/review/login", methods=["GET", "POST"])
    def review_login():
        if request.method == "POST":
            password = request.form.get("password", "")
            if password == review_password:
                session["review_authenticated"] = True
                return redirect(url_for("review_dashboard"))
            return render_template("review_login.html", error="Incorrect password"), 200
        return render_template("review_login.html", error=None)

    @app.route("/review/logout")
    def review_logout():
        session.pop("review_authenticated", None)
        return redirect(url_for("review_login"))

    # --- Clinician review routes ---

    @app.route("/review")
    @require_review_auth
    def review_dashboard():
        """Clinician 3-panel workstation with tabs."""
        try:
            sessions_list = get_all_sessions()
            stats = get_session_stats()

            risk_order = {"HIGH": 0, "MODERATE": 1, "LOW": 2}
            status_order = {"pending_review": 0, "flagged": 1, "reviewed": 2}
            sessions_list.sort(key=lambda s: (
                status_order.get(s.get("status", "pending_review"), 9),
                risk_order.get(s.get("highest_risk", "LOW"), 9),
            ))

            pending_synonyms = get_all_synonym_proposals(status="pending")
            pending_rules = get_all_rule_proposals(status="pending")
            approved_synonyms = get_all_synonym_proposals(status="approved")

            return render_template(
                "review.html",
                sessions=sessions_list,
                stats=stats,
                pending_synonyms=pending_synonyms,
                pending_rules=pending_rules,
                approved_synonyms=approved_synonyms,
                high_flags=list(HIGH_RISK_FLAGS),
                moderate_flags=list(MODERATE_RISK_FLAGS),
                combination_rules=list(COMBINATION_RULES),
            )
        except Exception:
            logger.exception("Error in /review")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/session-data/<session_id>")
    @require_review_auth
    def api_session_data(session_id):
        """Return full session JSON for the center panel."""
        try:
            if not _validate_session_id(session_id):
                return jsonify({"error": "Invalid session ID"}), 404

            sess = get_session(session_id)
            if sess is None:
                return jsonify({"error": "Session not found"}), 404

            exchanges = get_exchanges(session_id)
            synonym_proposals = get_synonym_proposals_for_session(session_id)
            rule_proposals = get_pending_rule_proposals(DB_PATH)

            return jsonify({
                "session": sess,
                "exchanges": exchanges,
                "synonym_proposals": synonym_proposals,
                "rule_proposals": rule_proposals,
            })
        except Exception:
            logger.exception("Error in /api/review/session-data")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/classifier-data")
    @require_review_auth
    def api_classifier_data():
        """Return current classifier flag lists and combination rules."""
        try:
            return jsonify({
                "high_flags": list(HIGH_RISK_FLAGS),
                "moderate_flags": list(MODERATE_RISK_FLAGS),
                "combination_rules": [
                    {"flags": r["flags"], "level": r["level"], "source": r.get("source", "unknown")}
                    for r in COMBINATION_RULES
                ],
            })
        except Exception:
            logger.exception("Error in /api/review/classifier-data")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/exchange/<int:exchange_id>", methods=["POST"])
    @require_review_auth
    def api_review_exchange(exchange_id):
        """Update an exchange's review status."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            action = data.get("action")
            if action not in VALID_REVIEW_ACTIONS:
                return jsonify({"error": "Invalid action"}), 400

            corrected_risk = data.get("corrected_risk_level")
            if corrected_risk is not None and corrected_risk not in VALID_RISK_LEVELS:
                return jsonify({"error": "Invalid corrected_risk_level"}), 400

            corrected_care = data.get("corrected_care_level")
            if corrected_care is not None and corrected_care not in VALID_CARE_LEVELS:
                return jsonify({"error": "Invalid corrected_care_level"}), 400

            reason = data.get("reason")
            if reason is not None:
                reason = sanitize_input(str(reason), max_length=500)

            update_exchange_review(
                exchange_id=exchange_id,
                review_status=action,
                corrected_risk_level=corrected_risk,
                corrected_care_level=corrected_care,
                review_reason=reason,
            )
            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/exchange")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/session/<session_id>", methods=["POST"])
    @require_review_auth
    def api_review_session(session_id):
        """Update a session's review status and notes."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            status = data.get("status")
            if status not in VALID_SESSION_STATUSES:
                return jsonify({"error": "Invalid status"}), 400

            notes = data.get("notes")
            if notes is not None:
                notes = sanitize_input(str(notes), max_length=2000)

            update_session_status(
                session_id=session_id,
                status=status,
                reviewer_notes=notes,
            )
            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/session")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/synonym/<int:proposal_id>", methods=["POST"])
    @require_review_auth
    def api_review_synonym(proposal_id):
        """Approve or reject a synonym proposal."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            action = data.get("action")
            if action not in VALID_PROPOSAL_ACTIONS:
                return jsonify({"error": "Invalid action"}), 400

            if action == "approve":
                approve_synonym(DB_PATH, proposal_id)
            else:
                reject_proposal(DB_PATH, proposal_id)

            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/synonym")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/rule/<int:proposal_id>", methods=["POST"])
    @require_review_auth
    def api_review_rule(proposal_id):
        """Approve or reject a rule proposal."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            action = data.get("action")
            if action not in VALID_PROPOSAL_ACTIONS:
                return jsonify({"error": "Invalid action"}), 400

            if action == "approve":
                approve_rule_proposal(DB_PATH, proposal_id)
            else:
                reject_proposal(DB_PATH, proposal_id)

            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/rule")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/proposals")
    @require_review_auth
    def api_get_proposals():
        """Return all pending synonym and rule proposals."""
        try:
            synonyms = get_pending_proposals(DB_PATH, proposal_type="synonym")
            rules = get_pending_proposals(DB_PATH, proposal_type="rule")
            return jsonify({"synonyms": synonyms, "rules": rules})
        except Exception:
            logger.exception("Error in /api/review/proposals")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/rewrite", methods=["POST"])
    @require_review_auth
    def api_review_rewrite():
        """Generate an AI-suggested rewrite of an assistant response."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            user_input = data.get("user_input")
            current_response = data.get("current_response")
            if not user_input or not current_response:
                return jsonify({"error": "user_input and current_response are required"}), 400

            if not has_api_key or client is None:
                return jsonify({"error": "API key not configured"}), 503

            intake_context = data.get("intake_context", "")
            rewrite_response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system="You are a clinical triage assistant. Rewrite this response to be more helpful, proportionate, and actionable. Keep it concise. Do not diagnose. Match urgency to the actual symptoms described.",
                messages=[{"role": "user", "content": f"Patient said: {user_input}\n\nIntake context: {intake_context}\n\nCurrent AI response:\n{current_response}\n\nProvide a better rewrite:"}],
                temperature=0.5,
            )
            rewrite = rewrite_response.content[0].text.strip()
            return jsonify({"rewrite": rewrite})
        except Exception:
            logger.exception("Error in /api/review/rewrite")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/add-synonym", methods=["POST"])
    @require_review_auth
    def api_add_synonym():
        """Directly add a synonym to the classifier."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            phrase = data.get("phrase")
            category = data.get("category")
            synonym_for = data.get("synonym_for")
            if not phrase or not category or not synonym_for:
                return jsonify({"error": "phrase, category, and synonym_for are required"}), 400

            if category not in ("HIGH", "MODERATE"):
                return jsonify({"error": "category must be HIGH or MODERATE"}), 400

            save_synonym_proposal(
                db_path=DB_PATH, patient_phrase=phrase,
                gpt_risk_level=category, local_risk_level="LOW",
                proposed_category=category, proposed_synonym_for=synonym_for,
                session_id="clinician_manual",
            )
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            try:
                row = conn.execute(
                    "SELECT id FROM synonym_proposals WHERE patient_phrase = ? ORDER BY id DESC LIMIT 1",
                    (phrase,),
                ).fetchone()
                if row:
                    approve_synonym(DB_PATH, row[0])
                    apply_approved_synonyms(DB_PATH, classifier_path)
            finally:
                conn.close()

            return jsonify({"status": "ok", "phrase": phrase, "added_to": category})
        except Exception:
            logger.exception("Error in /api/review/add-synonym")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/add-rule", methods=["POST"])
    @require_review_auth
    def api_add_rule():
        """Directly add a combination rule."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            flags = data.get("flags")
            level = data.get("level")
            if not flags or not level:
                return jsonify({"error": "flags and level are required"}), 400

            if level not in ("HIGH", "MODERATE"):
                return jsonify({"error": "level must be HIGH or MODERATE"}), 400

            rule_dict = {"flags": flags, "level": level, "source": "clinician_approved"}
            apply_combination_rule(rule_dict)

            save_rule_proposal(
                db_path=DB_PATH, proposal_type="combination_rule",
                description=" + ".join(flags) + " should be " + level,
                supporting_evidence=[], proposed_rule={"flags": flags, "level": level},
            )
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            try:
                row = conn.execute(
                    "SELECT id FROM rule_proposals ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    approve_rule_proposal(DB_PATH, row[0])
            finally:
                conn.close()

            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/add-rule")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/impact/<path:phrase>")
    @require_review_auth
    def api_impact(phrase):
        """Return impact count for a phrase."""
        try:
            result = count_similar_exchanges(phrase)
            return jsonify(result)
        except Exception:
            logger.exception("Error in /api/review/impact")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/analyze/<session_id>")
    @require_review_auth
    def api_analyze_session(session_id):
        """Return AI analysis for a session, with caching."""
        try:
            if not _validate_session_id(session_id):
                return jsonify({"error": "Invalid session ID"}), 404

            refresh = request.args.get("refresh") == "true"

            if not refresh:
                cached = get_analysis(session_id)
                if cached:
                    return jsonify(cached)

            sess = get_session(session_id)
            if sess is None:
                return jsonify({"error": "Session not found"}), 404

            if not has_api_key or client is None:
                return jsonify({"clinical_summary": "Analysis unavailable — API key not configured."}), 503

            exchanges = get_exchanges(session_id)
            flags = {"high": list(HIGH_RISK_FLAGS), "moderate": list(MODERATE_RISK_FLAGS)}
            result = analyze_session(client, sess, exchanges, flags)

            save_analysis(session_id, result)
            return jsonify(result)
        except Exception:
            logger.exception("Error in /api/review/analyze")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/bulk-synonyms", methods=["POST"])
    @require_review_auth
    def api_bulk_synonyms():
        """Generate bulk synonym suggestions for a phrase."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            phrase = data.get("phrase")
            mapped_to = data.get("mapped_to")
            category = data.get("category")
            if not phrase or not mapped_to or not category:
                return jsonify({"error": "phrase, mapped_to, and category are required"}), 400

            if not has_api_key or client is None:
                return jsonify({"error": "API key not configured"}), 503

            suggestions = generate_bulk_synonyms(client, phrase, mapped_to, category)
            return jsonify({"suggestions": suggestions})
        except Exception:
            logger.exception("Error in /api/review/bulk-synonyms")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/save-correction", methods=["POST"])
    @require_review_auth
    def api_save_correction():
        """Save a clinician's corrected response for an exchange."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            exchange_id = data.get("exchange_id")
            if exchange_id is None:
                return jsonify({"error": "exchange_id is required"}), 400

            corrected_risk = data.get("corrected_risk_level")
            if corrected_risk and corrected_risk not in VALID_RISK_LEVELS:
                return jsonify({"error": "Invalid corrected_risk_level"}), 400

            corrected_care = data.get("corrected_care_level")
            if corrected_care and corrected_care not in VALID_CARE_LEVELS:
                return jsonify({"error": "Invalid corrected_care_level"}), 400

            reason = data.get("reason", "")
            if reason:
                reason = sanitize_input(str(reason), max_length=500)

            update_exchange_review(
                exchange_id=exchange_id,
                review_status="corrected",
                corrected_risk_level=corrected_risk,
                corrected_care_level=corrected_care,
                review_reason=reason,
            )
            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/save-correction")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/review/remove-flag", methods=["POST"])
    @require_review_auth
    def api_remove_flag():
        """Remove a flag from the in-memory classifier lists."""
        try:
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "JSON body required"}), 400

            phrase = data.get("phrase")
            category = data.get("category")
            if not phrase or not category:
                return jsonify({"error": "phrase and category are required"}), 400

            if category == "HIGH" and phrase in HIGH_RISK_FLAGS:
                HIGH_RISK_FLAGS.remove(phrase)
            elif category == "MODERATE" and phrase in MODERATE_RISK_FLAGS:
                MODERATE_RISK_FLAGS.remove(phrase)
            else:
                return jsonify({"error": "Flag not found"}), 404

            return jsonify({"status": "ok"})
        except Exception:
            logger.exception("Error in /api/review/remove-flag")
            return jsonify({"error": "An unexpected error occurred."}), 500

    return app
