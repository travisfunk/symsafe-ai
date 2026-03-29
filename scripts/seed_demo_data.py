"""Seed the SymSafe database with realistic demo data for the clinician dashboard."""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta

from symsafe.config import DB_PATH
from symsafe.store import (
    init_db, save_session, save_exchange, update_session,
    update_session_status, get_session, save_analysis,
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


def _seed_analyses(session_ids):
    """Insert pre-computed AI analyses for demo sessions."""
    s1, s2, s3, s4, s5 = session_ids

    save_analysis(s1, {
        "clinical_summary": "Patient presented with acute-onset chest pain (severity 8/10) with progressive radiating left arm pain. History of heart disease and aspirin use. AI appropriately escalated to emergency and recommended 911. This presentation is consistent with acute coronary syndrome and warrants immediate evaluation.",
        "risk_assessment": {"ai_risk_was_appropriate": True, "explanation": "Both exchanges correctly identified as HIGH risk with emergency care level. The escalation from chest pain to radiating arm pain was handled well.", "suggested_risk": "HIGH", "reasoning": "Chest pain radiating to left arm in a patient with cardiac history is a classic ACS presentation."},
        "response_quality": [
            {"exchange_index": 0, "score": "good", "feedback": "Appropriate urgency without being alarmist. Good follow-up questions about pain character and aggravating factors.", "suggested_improvement": "", "missed_questions": []},
            {"exchange_index": 1, "score": "good", "feedback": "Correct 911 recommendation for radiating chest pain. Mentioned aspirin appropriately given patient's medication history.", "suggested_improvement": "", "missed_questions": []}
        ],
        "differential_considerations": ["Acute coronary syndrome (STEMI/NSTEMI) — most consistent with presentation", "Aortic dissection — less likely but should be ruled out", "Pulmonary embolism — consider if ECG is normal"],
        "synonym_suggestions": [],
        "response_templates": [],
        "intake_observations": "Patient reported severity 8/10 with worsening trajectory and cardiac history. Intake correctly captured high-acuity presentation.",
        "review_priority": "urgent",
        "priority_reason": "Potential acute cardiac event requiring verification of emergency follow-through",
        "pattern_notes": "Cardiac presentations with radiating pain should always trigger emergency protocol. This session is a good example of appropriate escalation."
    })

    save_analysis(s2, {
        "clinical_summary": "Patient presented with persistent headache (3 days, severity 6/10) unresponsive to ibuprofen, which subsequently developed visual symptoms (spots in vision). AI appropriately escalated from primary_care to urgent_care when vision changes were reported. The headache + vision combination warrants same-day evaluation.",
        "risk_assessment": {"ai_risk_was_appropriate": True, "explanation": "Initial MODERATE for persistent headache was appropriate. Escalation to HIGH when vision changes appeared was correct per combination rules.", "suggested_risk": "HIGH", "reasoning": "Headache with visual symptoms could indicate increased intracranial pressure, migraine with aura, or more serious pathology."},
        "response_quality": [
            {"exchange_index": 0, "score": "good", "feedback": "Good reassurance while taking the symptom seriously. Relevant follow-up questions about pain type and location.", "suggested_improvement": "", "missed_questions": ["Any nausea or vomiting?"]},
            {"exchange_index": 1, "score": "needs_improvement", "feedback": "Correctly escalated to urgent care, but could have been more specific about what type of evaluation to seek.", "suggested_improvement": "A persistent headache combined with vision changes like seeing spots should be evaluated promptly. I'd recommend going to an urgent care clinic today, or calling your doctor's office for a same-day appointment. They may want to check your blood pressure and do a neurological exam.", "missed_questions": ["Are the spots in both eyes or just one?", "Any numbness or tingling?"]}
        ],
        "differential_considerations": ["Migraine with aura — most likely given age and presentation", "Hypertensive crisis — check BP", "Intracranial mass — less likely but should be evaluated", "Temporal arteritis — if patient is over 50"],
        "synonym_suggestions": [
            {"phrase": "bad headache", "should_map_to": "headache", "category": "MODERATE", "reason": "Patients frequently describe severe headaches as 'bad headache' — the classifier should catch this common phrasing.", "similar_phrases": ["terrible headache", "awful headache", "really bad headache", "pounding headache"]},
            {"phrase": "spots in vision", "should_map_to": "vision changes", "category": "HIGH", "reason": "Visual disturbances like 'spots' should map to the existing 'vision changes' flag for combination rule triggering.", "similar_phrases": ["seeing spots", "floaters", "flashing lights", "blurry spots"]}
        ],
        "response_templates": [],
        "intake_observations": "Patient selected '2-3 days' for onset but the AI could have asked for more precision. Pain severity 6/10 with 'same' trajectory may understate the situation given the subsequent vision changes.",
        "review_priority": "needs_attention",
        "priority_reason": "Vision changes with headache — verify patient sought evaluation",
        "pattern_notes": "Headache + vision symptom combinations are a known escalation pattern. The classifier correctly has a combination rule for this."
    })

    save_analysis(s3, {
        "clinical_summary": "Patient presented with mild gastric discomfort (severity 3/10, 1 day duration) likely related to dietary cause. AI provided appropriate self-care guidance. Low-risk presentation requiring no medical intervention.",
        "risk_assessment": {"ai_risk_was_appropriate": True, "explanation": "LOW risk and self_care recommendation were appropriate for this mild, acute-onset GI complaint.", "suggested_risk": "LOW", "reasoning": "Mild stomach upset of short duration with no red flags is appropriately managed with self-care."},
        "response_quality": [
            {"exchange_index": 0, "score": "good", "feedback": "Excellent proportionate response. Provided practical self-care advice without over-medicalizing. Clear escalation criteria given.", "suggested_improvement": "", "missed_questions": []}
        ],
        "differential_considerations": ["Viral gastroenteritis — most likely", "Food-related GI upset — patient suspects this", "Food intolerance — if recurrent"],
        "synonym_suggestions": [],
        "response_templates": [],
        "intake_observations": "Straightforward low-acuity intake. No concerns.",
        "review_priority": "routine",
        "priority_reason": "Low-risk self-limiting presentation handled appropriately",
        "pattern_notes": ""
    })

    save_analysis(s4, {
        "clinical_summary": "Patient with asthma history presented with chest burning on coughing, sore throat, congestion, and low fever over 2-3 days with worsening trajectory. AI correctly identified this as likely upper respiratory infection and recommended primary care given the asthma comorbidity. MODERATE risk is appropriate.",
        "risk_assessment": {"ai_risk_was_appropriate": True, "explanation": "MODERATE risk with primary_care recommendation was appropriate. The asthma comorbidity correctly influenced the care level.", "suggested_risk": "MODERATE", "reasoning": "URI symptoms in an asthma patient warrant closer monitoring but are not urgent unless respiratory distress develops."},
        "response_quality": [
            {"exchange_index": 0, "score": "good", "feedback": "Good contextualization of chest burning as cough-related rather than cardiac. Appropriate concern about asthma history. Relevant follow-up questions.", "suggested_improvement": "", "missed_questions": []},
            {"exchange_index": 1, "score": "needs_improvement", "feedback": "Solid advice overall but could be more specific about when to seek urgent care for an asthma patient.", "suggested_improvement": "With the congestion, sore throat, and low fever on top of your asthma, this sounds like a cold or upper respiratory infection. Schedule an appointment with your doctor in the next day or two since respiratory infections can aggravate asthma.\n\nIn the meantime, stay hydrated and rest. If your breathing gets noticeably tighter, you're using your rescue inhaler more than every 4 hours, or your fever goes above 101, head to urgent care rather than waiting for your appointment.", "missed_questions": ["What is your current temperature?", "Do you have a peak flow meter?"]}
        ],
        "differential_considerations": ["Upper respiratory infection — most consistent", "Acute bronchitis — possible given chest symptoms", "Asthma exacerbation triggered by URI — monitor closely"],
        "synonym_suggestions": [
            {"phrase": "chest burns", "should_map_to": "chest pain", "category": "MODERATE", "reason": "Chest burning from coughing is common in URI but currently matches HIGH risk 'chest pain'. Consider creating a MODERATE-level synonym to avoid over-triaging.", "similar_phrases": ["burning in chest", "chest feels like burning", "my chest is on fire"]}
        ],
        "response_templates": [],
        "intake_observations": "Asthma noted in conditions — this correctly influenced the AI's recommendation to see a doctor rather than pure self-care.",
        "review_priority": "needs_attention",
        "priority_reason": "Asthma patient with respiratory symptoms — verify appropriate follow-up",
        "pattern_notes": "URI symptoms + asthma history is a common pattern that should default to primary_care. The 'chest burns' synonym issue highlights a classifier gap where cough-related chest burning triggers cardiac-level flags."
    })

    save_analysis(s5, {
        "clinical_summary": "Patient expressed hopelessness and suicidal ideation (severity 9/10, worsening over 1-2 weeks). AI correctly identified this as a mental health emergency and provided 988 crisis line and ER resources. Appropriate crisis response.",
        "risk_assessment": {"ai_risk_was_appropriate": True, "explanation": "HIGH risk with emergency care level was the only appropriate response for expressed suicidal ideation.", "suggested_risk": "HIGH", "reasoning": "Any expression of suicidal ideation requires immediate crisis intervention."},
        "response_quality": [
            {"exchange_index": 0, "score": "good", "feedback": "Excellent crisis response. Warm, non-judgmental tone. 988 hotline provided. ER option given. Open-ended follow-up offered.", "suggested_improvement": "", "missed_questions": []}
        ],
        "differential_considerations": ["Acute suicidal crisis — primary concern", "Major depressive episode — likely underlying", "Situational crisis — assess contributing factors"],
        "synonym_suggestions": [],
        "response_templates": [],
        "intake_observations": "Severity 9/10 with worsening trajectory for mental health concern should potentially auto-flag for immediate review.",
        "review_priority": "urgent",
        "priority_reason": "Suicidal ideation — verify crisis resources were provided and patient safety",
        "pattern_notes": "Mental health emergencies with severity 8+ and worsening trajectory should be auto-flagged for clinician review regardless of AI response quality."
    })

    return 5


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
    analysis_count = _seed_analyses(session_ids)

    exchange_count = 2 + 2 + 1 + 2 + 1  # per session
    print(f"Seeded: 5 sessions, {exchange_count} exchanges, {synonym_count} synonym proposals, {rule_count} rule proposals, {analysis_count} analyses")


if __name__ == "__main__":
    main()
