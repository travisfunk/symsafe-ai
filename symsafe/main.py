"""
main.py — CLI entrypoint that orchestrates the full triage session.

Coordinates all modules into a complete patient interaction: optional
guided intake, conversation loop with dual-layer risk assessment and
care routing, escalation tracking, session logging, and HTML report
generation at session end. This is the only module that performs user I/O.
"""

import sys
import datetime
import argparse

from symsafe.config import BASE_DIR, DB_PATH, get_client, load_base_prompt
from symsafe.risk_classifier import classify_risk, load_combination_rules_from_db, HIGH_RISK_FLAGS, MODERATE_RISK_FLAGS
from symsafe.symptom_tree import match_symptom_tree, load_symptom_tree
from symsafe.evaluator import run_auto_evaluation
from symsafe.agent import get_assistant_response
from symsafe.logger import create_log_file, log_interaction, log_session_summary, log_intake
from symsafe.care_router import get_care_guidance, merge_care_level, CARE_LEVEL_HIERARCHY
from symsafe.intake import run_intake, format_intake_context
from symsafe.report import generate_report, save_report
from symsafe.store import init_db, save_session, save_exchange
from symsafe.feedback import detect_classifier_gap, find_nearest_flag, save_synonym_proposal, generate_proposals

# Numeric ranking for comparing risk tiers when determining the session maximum.
RISK_HIERARCHY = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def render_ui_header(learning_mode):
    """Print the ASCII art session header to the console.

    Args:
        learning_mode: If True, displays the learning mode banner variant.
    """
    if learning_mode:
        print("""
╔═════════════════════════════════════════════════╗
║  SymSafe – Virtual Triage AI   🧠 LEARNING MODE ║
╚═════════════════════════════════════════════════╝
""")
    else:
        print("""
╔════════════════════════════════════════════════╗
║     SymSafe – Virtual Triage AI              ║
╚════════════════════════════════════════════════╝
""")
    print("💬 Type symptoms or questions | Type 'exit' to quit")
    if learning_mode:
        print("📘 LEARNING MODE ENABLED – Explanations will be included\n")


def print_assistant_response(reply, risk_level, follow_up_questions=None, care_level=None):
    """Display the assistant's response with risk banners and care guidance.

    Shows a contextual warning banner above the response for HIGH/MODERATE
    risk, the conversational reply, any follow-up questions, and actionable
    care guidance for non-self_care levels.

    Args:
        reply: The assistant's response text.
        risk_level: The merged risk level string.
        follow_up_questions: Optional list of follow-up question strings.
        care_level: Optional care level string for guidance display.
    """
    if "HIGH" in risk_level.upper():
        print("\n⚠️ IMPORTANT: Based on what you've described, please seek immediate medical attention or call 911.")
    elif "MODERATE" in risk_level.upper():
        print("\n📋 Consider scheduling an appointment with your healthcare provider about this.")
    else:
        print()
    print(f"🤖 AI Assistant:\n{reply}")
    if follow_up_questions:
        print("\nI'd like to understand more:")
        for q in follow_up_questions:
            print(f"  • {q}")
    if care_level and care_level != "self_care":
        guidance = get_care_guidance(care_level)
        print(f"\n📍 Where to go: {guidance['where']}")
        print(f"   Why: {guidance['why']}")
        print(f"💡 Right now: {guidance['right_now']}")
    print()


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
        return "🔴 HIGH RISK"
    elif winner == "MODERATE":
        return "🟡 MODERATE RISK"
    return "🟢 LOW RISK"


def print_session_summary(session_symptoms, session_highest_risk, session_message_count, session_highest_care_level=None):
    """Print a formatted session summary to the console at session end.

    Args:
        session_symptoms: List of all symptom strings collected during session.
        session_highest_risk: The highest risk tier reached ("HIGH", "MODERATE", "LOW").
        session_message_count: Total number of patient messages exchanged.
        session_highest_care_level: Optional highest care level from session.
    """
    if session_message_count == 0 or (session_message_count > 0 and not session_symptoms):
        print("\n👋 Session ended. No symptoms were discussed. Take care!")
        return

    if session_highest_risk == "HIGH":
        action = "Seek immediate medical evaluation"
    elif session_highest_risk == "MODERATE":
        action = "Schedule an appointment with your healthcare provider"
    else:
        action = "No urgent action needed — see a provider if symptoms develop"

    unique_symptoms = list(dict.fromkeys(session_symptoms))

    care_line = ""
    if session_highest_care_level and session_highest_care_level != "self_care":
        guidance = get_care_guidance(session_highest_care_level)
        care_line = f"\n📍 Recommended care: {guidance['where']}"

    print(f"""
╔═══════════════════════════════════════════════╗
║           SymSafe Session Summary             ║
╚═══════════════════════════════════════════════╝
📋 Symptoms discussed: {', '.join(unique_symptoms)}
⚠️ Highest risk level: {session_highest_risk}
💬 Messages exchanged: {session_message_count}
📌 Recommended action: {action}{care_line}

This summary is for your reference. Please share it with your
healthcare provider at your next visit.
""")


def main():
    """Run the full SymSafe triage session.

    Parses CLI arguments, initializes resources, optionally runs the
    guided intake, then enters the main conversation loop. Handles
    risk classification, care routing, escalation tracking, evaluation,
    logging, and report generation.
    """
    parser = argparse.ArgumentParser(description="SymSafe AI Triage Assistant")
    parser.add_argument("--learn", action="store_true", help="Enable learning mode")
    parser.add_argument("--intake", action="store_true", help="Start with guided intake questionnaire")
    args = parser.parse_args()
    learning_mode = args.learn

    init_db()

    # Load clinician-approved combination rules from the database
    load_combination_rules_from_db(DB_PATH)

    # Apply any approved synonym proposals to the classifier source file
    classifier_path = BASE_DIR / "symsafe" / "risk_classifier.py"
    generate_proposals(DB_PATH, classifier_path)

    client = get_client()

    try:
        base_prompt = load_base_prompt()
    except FileNotFoundError:
        print("Error: prompts/base_prompt.txt not found")
        sys.exit(1)

    symptom_tree = load_symptom_tree()

    # Set up logging
    log_dir = BASE_DIR / "logs"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = create_log_file(log_dir, timestamp)

    messages = [{"role": "system", "content": base_prompt}]

    # Session-level accumulators
    session_symptoms = []
    session_highest_risk = "LOW"
    session_message_count = 0
    session_highest_care_level = "self_care"
    exchange_index = 0

    # Conversation log for HTML report generation
    conversation_log = []
    session_follow_ups = []
    session_provider_questions = []

    # Tracks messages since last emergency/urgent_care recommendation.
    # After 3 messages without the patient seeking care, re-escalate.
    messages_since_escalation = 0
    last_escalation_care_level = None

    intake_answers = None

    render_ui_header(learning_mode)

    # Guided intake: --intake flag skips the yes/no prompt
    do_intake = args.intake
    if not do_intake:
        intake_choice = input("Would you like me to walk you through a few quick questions first? (yes/no) ").strip().lower()
        if intake_choice in ("exit", "quit"):
            print("Session ended.")
            return
        do_intake = intake_choice in ("yes", "y")

    if do_intake:
        intake_result = run_intake()
        if intake_result is None:
            print("Session ended.")
            return
        intake_answers = intake_result
        if intake_answers:
            context = format_intake_context(intake_answers)
            if context:
                messages.append({"role": "system", "content": context})
            # Seed session symptoms from intake answers
            if "concern" in intake_answers:
                session_symptoms.append(intake_answers["concern"].lower())
            if "location" in intake_answers and intake_answers["location"].lower() not in ("not applicable", "all over"):
                session_symptoms.append(intake_answers["location"].lower())
            log_intake(log_filename, intake_answers)
        else:
            log_intake(log_filename, {})
        print("Got it. Let's talk about what you're experiencing.\n")

    def end_session():
        print_session_summary(session_symptoms, session_highest_risk, session_message_count, session_highest_care_level)
        log_session_summary(log_filename, list(dict.fromkeys(session_symptoms)), session_highest_risk, session_message_count, session_highest_care_level)
        save_session(
            session_id=timestamp,
            intake_answers=intake_answers,
            highest_risk=session_highest_risk,
            highest_care_level=session_highest_care_level,
            message_count=session_message_count,
            session_symptoms=list(dict.fromkeys(session_symptoms)),
        )
        generate_proposals(DB_PATH, classifier_path)
        if session_message_count > 0:
            provider_qs = list(dict.fromkeys(session_provider_questions))
            if not provider_qs:
                provider_qs = [
                    "What do you think is causing these symptoms?",
                    "Are there any tests I should have done?",
                    "What should I watch for that would mean I need to come back?",
                ]
            report_html = generate_report(
                timestamp=timestamp,
                intake_answers=intake_answers,
                session_symptoms=session_symptoms,
                highest_risk=session_highest_risk,
                highest_care_level=session_highest_care_level,
                message_count=session_message_count,
                conversation_log=conversation_log,
                provider_questions=provider_qs,
            )
            reports_dir = BASE_DIR / "reports"
            report_path = save_report(report_html, reports_dir, timestamp)
            print(f"Patient report saved: reports/symsafe_report_{timestamp}.html")
            print("   Open this file in your browser to view or print it.")

    try:
        while True:
            user_input = input("You: ")
            user_input = user_input.strip()

            if not user_input:
                print("Please enter your symptoms or a question.")
                continue

            if len(user_input) > 1000:
                print("Input too long. Please keep your message under 1000 characters.")
                continue

            if user_input.lower() in ["exit", "quit"]:
                end_session()
                break

            # Re-escalate if patient hasn't sought care after 3+ messages
            if last_escalation_care_level in ("emergency", "urgent_care") and messages_since_escalation >= 3:
                care_word = "emergency care" if last_escalation_care_level == "emergency" else "urgent care"
                print(f"I recommended {care_word} 3 messages ago. If you haven't sought care yet, please prioritize that. I'm here if you need help, but getting medical attention is the most important next step.")
                messages_since_escalation = 0

            messages.append({"role": "user", "content": user_input})
            local_risk_level, local_risk_flags = classify_risk(user_input)

            # Match against curated symptom tree for static clinical references
            tree_matches = match_symptom_tree(user_input, symptom_tree)
            hint_message = None
            if tree_matches:
                matched_names = [m[0] for m in tree_matches]
                print(f"Matched: {', '.join(matched_names)}")
                guidance = "; ".join(f"{k}: {v}" for k, v in tree_matches)
                hint_message = {"role": "system", "content": f"Clinical reference for reported symptoms: {guidance}. Use this to inform your response, but still reply conversationally."}
                messages.append(hint_message)

            # Keep conversation history bounded to manage token costs
            if len(messages) > 21:
                messages = [messages[0]] + messages[-(20):]

            result = get_assistant_response(client, messages)

            # Remove temporary symptom tree hint to keep history clean
            if hint_message and hint_message in messages:
                messages.remove(hint_message)

            if result is None:
                print("Sorry, I couldn't process that. Please try again.")
                messages.pop()
                continue

            reply = result["response"]
            gpt_risk_level = result.get("risk_level", "LOW")
            gpt_risk_flags = result.get("risk_flags", [])
            follow_up_questions = result.get("follow_up_questions", [])
            provider_questions = result.get("provider_questions", [])
            gpt_care_level = result.get("care_level", "self_care")

            # Dual-layer risk merging: take the higher of local and GPT assessments
            merged_risk_level = _merge_risk(local_risk_level, gpt_risk_level)
            all_flags = list(dict.fromkeys(local_risk_flags + gpt_risk_flags))

            # Ensure care level is consistent with merged risk (safety-first)
            care_level = merge_care_level(merged_risk_level, gpt_care_level)

            # Store only the conversational reply in history (not the full JSON)
            messages.append({"role": "assistant", "content": reply})

            # Accumulate session data
            session_message_count += 1
            for flag in all_flags:
                session_symptoms.append(flag)
            if tree_matches:
                for m in tree_matches:
                    session_symptoms.append(m[0])

            # Track highest risk tier across the session
            merged_tier = "LOW"
            if "HIGH" in merged_risk_level.upper():
                merged_tier = "HIGH"
            elif "MODERATE" in merged_risk_level.upper():
                merged_tier = "MODERATE"
            if RISK_HIERARCHY.get(merged_tier, 0) > RISK_HIERARCHY.get(session_highest_risk, 0):
                session_highest_risk = merged_tier

            # Track highest care level across the session
            if CARE_LEVEL_HIERARCHY.get(care_level, 0) > CARE_LEVEL_HIERARCHY.get(session_highest_care_level, 0):
                session_highest_care_level = care_level

            # Escalation tracking: count messages since last emergency/urgent recommendation.
            # Reset if a new escalation occurs or if the topic shifts to non-clinical.
            if care_level in ("emergency", "urgent_care"):
                last_escalation_care_level = care_level
                messages_since_escalation = 0
            elif "LOW" in merged_risk_level.upper() and not tree_matches:
                last_escalation_care_level = None
                messages_since_escalation = 0
            else:
                if last_escalation_care_level:
                    messages_since_escalation += 1

            # Collect data for HTML report
            conversation_log.append({
                "user": user_input,
                "assistant": reply,
                "risk": merged_risk_level,
                "care_level": care_level,
                "risk_flags": all_flags,
            })
            if follow_up_questions:
                session_follow_ups.extend(follow_up_questions)
            if provider_questions:
                session_provider_questions.extend(provider_questions)

            print_assistant_response(reply, merged_risk_level, follow_up_questions, care_level)

            # Run AI evaluation only on clinically relevant messages
            is_clinical = "HIGH" in merged_risk_level.upper() or "MODERATE" in merged_risk_level.upper() or len(tree_matches) > 0
            if is_clinical:
                evaluation = run_auto_evaluation(client, user_input, reply, learning_mode)
            else:
                evaluation = None

            log_interaction(log_filename, user_input, merged_risk_level, all_flags, reply, evaluation, tree_matches, follow_up_questions, care_level)

            # Persist exchange to SQLite
            tree_match_keys = [m[0] for m in tree_matches] if tree_matches else []
            save_exchange(
                session_id=timestamp,
                exchange_index=exchange_index,
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
            exchange_index += 1

            # Detect classifier gaps and propose synonyms
            gap = detect_classifier_gap(
                user_input, local_risk_level, local_risk_flags,
                gpt_risk_level, gpt_risk_flags,
            )
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
                    session_id=timestamp,
                )

    except KeyboardInterrupt:
        print()
        end_session()


if __name__ == "__main__":
    main()
