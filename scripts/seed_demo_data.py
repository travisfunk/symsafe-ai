"""Seed the SymSafe database with realistic demo data for the clinician dashboard."""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta

from symsafe.config import DB_PATH
from symsafe.store import (
    init_db, save_session, save_exchange, update_session,
    update_session_status, get_session,
)
from symsafe.feedback import save_synonym_proposal, save_rule_proposal


DEMO_SESSION_IDS = [
    "20260325_091500",
    "20260325_143000",
    "20260326_100000",
    "20260326_154500",
    "20260327_083000",
]


def _sessions_exist():
    """Check if demo sessions are already in the database."""
    for sid in DEMO_SESSION_IDS:
        if get_session(sid) is not None:
            return True
    return False


def _clear_db():
    """Remove all data from the database tables."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM exchanges")
        conn.execute("DELETE FROM synonym_proposals")
        conn.execute("DELETE FROM rule_proposals")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        print("Cleared all existing data.")
    finally:
        conn.close()


def _seed_session_1():
    """HIGH risk, pending_review — chest pain with radiating arm pain."""
    sid = DEMO_SESSION_IDS[0]
    intake = {
        "concern": "chest pain", "location": "chest", "onset": "today",
        "severity": "8", "trajectory": "worse",
        "medications": "aspirin", "conditions": "heart disease",
    }
    save_session(
        session_id=sid, intake_answers=intake, highest_risk="HIGH",
        highest_care_level="emergency", message_count=2,
        session_symptoms=["chest pain", "radiating arm pain"],
        zip_code="46038",
    )
    save_exchange(
        session_id=sid, exchange_index=0,
        user_input="I've been having sharp chest pain since this morning and it's getting worse.",
        assistant_response="I want to make sure we take this seriously. Sharp chest pain that started this morning and is getting worse needs prompt medical attention. Please consider going to an emergency room, especially if the pain changes or spreads.\n\nA couple things that would help me understand better:\nIs the pain constant, or does it come and go?\nDoes anything make it worse — like breathing deeply, moving, or lying down?",
        local_risk_level="HIGH", local_risk_flags=["chest pain"],
        gpt_risk_level="HIGH", gpt_risk_flags=["chest pain", "sudden onset"],
        merged_risk_level="\U0001f534 HIGH RISK", care_level="emergency",
        follow_up_questions=["Is the pain constant or does it come and go?", "Does anything make it worse?"],
        evaluation="- [x] Safe\n- [x] Empathetic tone\n- [x] Avoided diagnosis\n- [x] Escalation offered\n- [x] Clear language",
        tree_matches=["chest pain"],
    )
    save_exchange(
        session_id=sid, exchange_index=1,
        user_input="The pain is spreading to my left arm now.",
        assistant_response="Chest pain that spreads to your left arm is something that needs immediate attention. Please call 911 or have someone drive you to the nearest emergency room right now. Don't wait to see if it gets better.\n\nWhile you wait for help, try to sit down and stay calm. If you have aspirin and aren't allergic, your doctor may have told you to take one in situations like this.",
        local_risk_level="HIGH", local_risk_flags=["chest pain"],
        gpt_risk_level="HIGH", gpt_risk_flags=["chest pain", "radiating arm pain"],
        merged_risk_level="\U0001f534 HIGH RISK", care_level="emergency",
        follow_up_questions=[],
        evaluation="- [x] Safe\n- [x] Empathetic tone\n- [x] Avoided diagnosis\n- [x] Escalation offered\n- [x] Clear language",
        tree_matches=["chest pain"],
    )
    return sid


def _seed_session_2():
    """MODERATE risk escalating to HIGH — headache with vision changes."""
    sid = DEMO_SESSION_IDS[1]
    intake = {
        "concern": "pain", "location": "head", "onset": "2-3 days",
        "severity": "6", "trajectory": "same",
        "medications": "ibuprofen", "conditions": "none",
    }
    save_session(
        session_id=sid, intake_answers=intake, highest_risk="HIGH",
        highest_care_level="urgent_care", message_count=2,
        session_symptoms=["persistent headache", "vision changes"],
    )
    save_exchange(
        session_id=sid, exchange_index=0,
        user_input="I've had a bad headache for a few days and nothing helps.",
        assistant_response="That sounds really frustrating, especially when the usual remedies aren't helping. A headache that hangs on for several days is worth paying attention to.\n\nA couple things that would help me understand better:\nCan you describe the pain — is it throbbing, pressure, or sharp?\nIs it on one side of your head or all over?",
        local_risk_level="LOW", local_risk_flags=[],
        gpt_risk_level="MODERATE", gpt_risk_flags=["persistent headache"],
        merged_risk_level="\U0001f7e1 MODERATE RISK", care_level="primary_care",
        follow_up_questions=["Can you describe the type of pain?", "Is it on one side or all over?"],
        evaluation=None,
        tree_matches=[],
    )
    save_exchange(
        session_id=sid, exchange_index=1,
        user_input="I'm also seeing some spots in my vision.",
        assistant_response="A persistent headache combined with vision changes like seeing spots is something that should be evaluated by a doctor today. I'd recommend going to an urgent care clinic or calling your doctor's office to get a same-day appointment.\n\nThis doesn't necessarily mean something is seriously wrong, but headaches with visual symptoms should be checked out promptly to be safe.",
        local_risk_level="HIGH", local_risk_flags=["vision changes"],
        gpt_risk_level="HIGH", gpt_risk_flags=["headache", "vision changes"],
        merged_risk_level="\U0001f534 HIGH RISK", care_level="urgent_care",
        follow_up_questions=["Are the spots constant or do they come and go?"],
        evaluation="- [x] Safe\n- [x] Empathetic tone\n- [x] Avoided diagnosis\n- [x] Escalation offered\n- [x] Clear language",
        tree_matches=[],
    )
    return sid


def _seed_session_3():
    """LOW risk, reviewed — mild stomach upset."""
    sid = DEMO_SESSION_IDS[2]
    intake = {
        "concern": "digestive", "location": "stomach", "onset": "yesterday",
        "severity": "3", "trajectory": "same",
        "medications": "none", "conditions": "none",
    }
    save_session(
        session_id=sid, intake_answers=intake, highest_risk="LOW",
        highest_care_level="self_care", message_count=1,
        session_symptoms=[],
    )
    save_exchange(
        session_id=sid, exchange_index=0,
        user_input="My stomach has been a little upset since yesterday, maybe something I ate.",
        assistant_response="That sounds like it could be a mild stomach bug or a reaction to something you ate. Since it's only been a day and the discomfort is mild, you can probably manage this at home.\n\nStick to bland foods like toast, rice, or bananas, and make sure you're staying hydrated. Avoid spicy, greasy, or heavy foods for a day or two.\n\nIf it doesn't improve in 2-3 days, or if you develop a fever, vomiting, or the pain gets significantly worse, that's when you'd want to check in with your doctor.",
        local_risk_level="LOW", local_risk_flags=[],
        gpt_risk_level="LOW", gpt_risk_flags=[],
        merged_risk_level="\U0001f7e2 LOW RISK", care_level="self_care",
        follow_up_questions=["Have you noticed any other symptoms like nausea or fever?"],
        evaluation=None,
        tree_matches=[],
    )
    update_session_status(sid, "reviewed", "Appropriate self-care recommendation. No concerns.")
    return sid


def _seed_session_4():
    """MODERATE risk, pending_review — cold symptoms with chest burning."""
    sid = DEMO_SESSION_IDS[3]
    intake = {
        "concern": "breathing", "location": "chest, throat", "onset": "2-3 days",
        "severity": "5", "trajectory": "worse",
        "medications": "none", "conditions": "asthma",
    }
    save_session(
        session_id=sid, intake_answers=intake, highest_risk="MODERATE",
        highest_care_level="primary_care", message_count=2,
        session_symptoms=["chest burning", "sore throat", "fever", "congestion"],
    )
    save_exchange(
        session_id=sid, exchange_index=0,
        user_input="My chest burns when I cough and my throat is really sore.",
        assistant_response="That sounds really uncomfortable. Chest burning with coughing is pretty common when you have a sore throat or upper respiratory symptoms — the coughing itself can irritate the muscles and lining of your chest.\n\nSince you mentioned you have asthma, I want to make sure we keep an eye on this.\n\nIs the burning only when you cough, or do you feel it at other times too?\nAre you using your inhaler more than usual?",
        local_risk_level="MODERATE", local_risk_flags=["burn"],
        gpt_risk_level="MODERATE", gpt_risk_flags=["chest burning", "sore throat"],
        merged_risk_level="\U0001f7e1 MODERATE RISK", care_level="primary_care",
        follow_up_questions=["Is the burning only when you cough?", "Are you using your inhaler more than usual?"],
        evaluation=None,
        tree_matches=[],
    )
    save_exchange(
        session_id=sid, exchange_index=1,
        user_input="I've also been really congested and have a low fever.",
        assistant_response="With the sore throat, chest burning from coughing, congestion, and now a low fever, this sounds like it could be a cold or upper respiratory infection. Since you have asthma, it would be a good idea to schedule an appointment with your doctor in the next day or two — respiratory infections can sometimes aggravate asthma.\n\nIn the meantime, rest and stay hydrated. Warm liquids like tea or broth can help with the congestion and sore throat.\n\nHow high is the fever? And is your breathing feeling tighter than usual?",
        local_risk_level="MODERATE", local_risk_flags=["fever"],
        gpt_risk_level="MODERATE", gpt_risk_flags=["fever", "congestion"],
        merged_risk_level="\U0001f7e1 MODERATE RISK", care_level="primary_care",
        follow_up_questions=["How high is the fever?", "Is your breathing feeling tighter than usual?"],
        evaluation=None,
        tree_matches=[],
    )
    return sid


def _seed_session_5():
    """HIGH risk, flagged — mental health crisis."""
    sid = DEMO_SESSION_IDS[4]
    intake = {
        "concern": "mental health", "location": "head", "onset": "1-2 weeks",
        "severity": "9", "trajectory": "worse",
        "medications": "none", "conditions": "none",
    }
    save_session(
        session_id=sid, intake_answers=intake, highest_risk="HIGH",
        highest_care_level="emergency", message_count=1,
        session_symptoms=["suicidal ideation", "hopelessness"],
    )
    save_exchange(
        session_id=sid, exchange_index=0,
        user_input="I've been feeling really hopeless and I don't see the point anymore.",
        assistant_response="I hear you, and I'm really glad you're sharing this with me. What you're feeling matters, and you don't have to go through this alone.\n\nIf you're having thoughts of hurting yourself, please reach out to the 988 Suicide and Crisis Lifeline right now — call or text 988. They're available 24/7 and they can help.\n\nYou can also go to your nearest emergency room if you feel you're in immediate danger.\n\nWould you like to tell me more about what you've been going through?",
        local_risk_level="HIGH", local_risk_flags=["suicidal"],
        gpt_risk_level="HIGH", gpt_risk_flags=["suicidal ideation", "hopelessness"],
        merged_risk_level="\U0001f534 HIGH RISK", care_level="emergency",
        follow_up_questions=["Would you like to tell me more about what you've been going through?"],
        evaluation="- [x] Safe\n- [x] Empathetic tone\n- [x] Avoided diagnosis\n- [x] Escalation offered\n- [x] Clear language\nExcellent crisis response with appropriate resources.",
        tree_matches=[],
    )
    update_session_status(sid, "flagged", "Patient expressing suicidal ideation. Verify crisis resources were provided.")
    return sid


def _seed_synonym_proposals(session_ids):
    """Insert synonym proposals with a mix of statuses."""
    s1, s2, s3, s4, s5 = session_ids

    # 1. pending — splitting headache
    save_synonym_proposal(
        db_path=None, patient_phrase="splitting headache",
        gpt_risk_level="HIGH", local_risk_level="LOW",
        proposed_category="HIGH", proposed_synonym_for="headache",
        session_id=s2,
    )
    # 2. pending — bad headache
    save_synonym_proposal(
        db_path=None, patient_phrase="bad headache",
        gpt_risk_level="MODERATE", local_risk_level="LOW",
        proposed_category="MODERATE", proposed_synonym_for="headache",
        session_id=s2,
    )
    # 3. pending — chest burns
    save_synonym_proposal(
        db_path=None, patient_phrase="chest burns",
        gpt_risk_level="HIGH", local_risk_level="MODERATE",
        proposed_category="HIGH", proposed_synonym_for="chest pain",
        session_id=s4,
    )
    # 4. approved — heart is racing
    save_synonym_proposal(
        db_path=None, patient_phrase="heart is racing",
        gpt_risk_level="HIGH", local_risk_level="LOW",
        proposed_category="HIGH", proposed_synonym_for="heart racing",
        session_id=s1,
    )
    # Update #4 to approved
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            "UPDATE synonym_proposals SET status = 'approved', reviewed_by = 'clinician' "
            "WHERE patient_phrase = 'heart is racing' AND session_id = ?", (s1,)
        )
        conn.commit()
    finally:
        conn.close()

    # 5. rejected — tummy ache
    save_synonym_proposal(
        db_path=None, patient_phrase="tummy ache",
        gpt_risk_level="MODERATE", local_risk_level="LOW",
        proposed_category="MODERATE", proposed_synonym_for="stomach",
        session_id=s3,
    )
    # Update #5 to rejected
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            "UPDATE synonym_proposals SET status = 'rejected', reviewed_by = 'clinician' "
            "WHERE patient_phrase = 'tummy ache' AND session_id = ?", (s3,)
        )
        conn.commit()
    finally:
        conn.close()

    return 5


def _seed_rule_proposals(session_ids):
    """Insert rule proposals."""
    s1, s2, s3, s4, s5 = session_ids

    save_rule_proposal(
        db_path=DB_PATH,
        proposal_type="combination_rule",
        description="headache + vision changes should be HIGH",
        supporting_evidence=[s2],
        proposed_rule={"flags": ["headache", "vision changes"], "level": "HIGH"},
    )
    save_rule_proposal(
        db_path=DB_PATH,
        proposal_type="combination_rule",
        description="chest pain + arm pain + sweating should be HIGH",
        supporting_evidence=[s1],
        proposed_rule={"flags": ["chest pain", "arm pain", "sweating"], "level": "HIGH"},
    )
    return 2


def main():
    parser = argparse.ArgumentParser(description="Seed SymSafe database with demo data")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()

    init_db()

    if args.clear:
        _clear_db()

    if _sessions_exist() and not args.clear:
        print("Demo data already exists. Use --clear to wipe and re-seed.")
        return

    seed_all()


def seed_all():
    """Insert all demo data. Can be called programmatically (e.g. on app startup)."""
    s1 = _seed_session_1()
    s2 = _seed_session_2()
    s3 = _seed_session_3()
    s4 = _seed_session_4()
    s5 = _seed_session_5()
    session_ids = [s1, s2, s3, s4, s5]

    synonym_count = _seed_synonym_proposals(session_ids)
    rule_count = _seed_rule_proposals(session_ids)

    exchange_count = 2 + 2 + 1 + 2 + 1  # per session
    print(f"Seeded: 5 sessions, {exchange_count} exchanges, {synonym_count} synonym proposals, {rule_count} rule proposals")


if __name__ == "__main__":
    main()
