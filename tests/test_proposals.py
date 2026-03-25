import json
import shutil
import tempfile
from pathlib import Path

import pytest

from symsafe.store import init_db, save_session, save_exchange, update_exchange_review
from symsafe.feedback import (
    apply_approved_synonyms,
    approve_synonym,
    detect_combination_patterns,
    generate_proposals,
    get_pending_rule_proposals,
    save_rule_proposal,
    save_synonym_proposal,
    approve_rule_proposal,
)
from symsafe.risk_classifier import (
    classify_risk,
    apply_combination_rule,
    COMBINATION_RULES,
)

# Path to the real risk_classifier.py for copying into temp directories.
REAL_CLASSIFIER = Path(__file__).resolve().parent.parent / "symsafe" / "risk_classifier.py"


@pytest.fixture
def db_env():
    """Provide a temp database and a temp copy of risk_classifier.py."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path=db_path)
        classifier_path = Path(tmpdir) / "risk_classifier.py"
        shutil.copy(str(REAL_CLASSIFIER), str(classifier_path))
        yield db_path, classifier_path


@pytest.fixture
def db_path():
    """Provide a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        init_db(db_path=path)
        yield path


class TestApplyApprovedSynonym:
    def test_applies_approved_synonym_to_high(self, db_env):
        db_path, classifier_path = db_env
        save_synonym_proposal(
            db_path, "chest is on fire", "HIGH", "LOW",
            "HIGH", "chest pain", "session1",
        )
        approve_synonym(db_path, 1)
        result = apply_approved_synonyms(db_path, classifier_path)
        assert len(result) == 1
        assert result[0]["phrase"] == "chest is on fire"
        assert result[0]["added_to"] == "HIGH"
        content = classifier_path.read_text(encoding="utf-8")
        assert '"chest is on fire"' in content
        assert content.index('"chest is on fire"') < content.index("MODERATE_RISK_FLAGS")

    def test_applies_approved_synonym_to_moderate(self, db_env):
        db_path, classifier_path = db_env
        save_synonym_proposal(
            db_path, "throwing up constantly", "MODERATE", "LOW",
            "MODERATE", "can't keep food down", "session1",
        )
        approve_synonym(db_path, 1)
        result = apply_approved_synonyms(db_path, classifier_path)
        assert len(result) == 1
        assert result[0]["added_to"] == "MODERATE"
        content = classifier_path.read_text(encoding="utf-8")
        assert '"throwing up constantly"' in content

    def test_skips_already_existing_synonym(self, db_env):
        db_path, classifier_path = db_env
        # "chest pain" already exists in HIGH_RISK_FLAGS
        save_synonym_proposal(
            db_path, "chest pain", "HIGH", "LOW",
            "HIGH", "chest pain", "session1",
        )
        approve_synonym(db_path, 1)
        result = apply_approved_synonyms(db_path, classifier_path)
        assert len(result) == 0

    def test_marks_as_applied(self, db_env):
        db_path, classifier_path = db_env
        save_synonym_proposal(
            db_path, "chest is on fire", "HIGH", "LOW",
            "HIGH", "chest pain", "session1",
        )
        approve_synonym(db_path, 1)
        apply_approved_synonyms(db_path, classifier_path)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status FROM synonym_proposals WHERE id = 1").fetchone()
        conn.close()
        assert dict(row)["status"] == "applied"

    def test_returns_empty_when_nothing_approved(self, db_env):
        db_path, classifier_path = db_env
        result = apply_approved_synonyms(db_path, classifier_path)
        assert result == []


class TestCombinationRules:
    def test_combination_rule_escalates_risk(self):
        level, flags = classify_risk("I have a headache and vision changes")
        assert "HIGH" in level.upper()

    def test_combination_partial_match_no_escalation(self):
        level, flags = classify_risk("I have a headache")
        assert "HIGH" not in level.upper()

    def test_combination_flags_included_in_result(self):
        level, flags = classify_risk("I have a headache and vision changes")
        combo_flags = [f for f in flags if f.startswith("combination:")]
        assert len(combo_flags) >= 1
        assert "headache" in combo_flags[0]
        assert "vision changes" in combo_flags[0]

    def test_apply_combination_rule_at_runtime(self):
        original_len = len(COMBINATION_RULES)
        test_rule = {"flags": ["elbow pain", "wrist pain"], "level": "MODERATE", "source": "test"}
        try:
            apply_combination_rule(test_rule)
            level, flags = classify_risk("I have elbow pain and wrist pain")
            assert "MODERATE" in level.upper()
        finally:
            # Restore original state
            while len(COMBINATION_RULES) > original_len:
                COMBINATION_RULES.pop()

    def test_classify_risk_still_works_without_combinations(self):
        level, flags = classify_risk("I have chest pain")
        assert "HIGH" in level.upper()
        assert "chest pain" in flags

        level, flags = classify_risk("I have a fever")
        assert "MODERATE" in level.upper()
        assert "fever" in flags

        level, flags = classify_risk("Hello there")
        assert "LOW" in level.upper()
        assert len(flags) == 0


class TestDetectCombinationPatterns:
    def _setup_corrected_exchanges(self, db_path, flag_combo, count, session_prefix="sess"):
        """Helper to insert sessions and corrected exchanges."""
        for i in range(count):
            sid = f"{session_prefix}_{i}"
            save_session(
                session_id=sid, intake_answers=None, highest_risk="LOW",
                highest_care_level="self_care", message_count=1,
                session_symptoms=[], db_path=db_path,
            )
            save_exchange(
                session_id=sid, exchange_index=0,
                user_input="test input", assistant_response="test response",
                local_risk_level="LOW", local_risk_flags=flag_combo[:1],
                gpt_risk_level="LOW", gpt_risk_flags=flag_combo[1:],
                merged_risk_level="LOW", care_level="self_care",
                follow_up_questions=[], evaluation=None, tree_matches=[],
                db_path=db_path,
            )
            # Get the exchange id (it's the (i+1)th exchange inserted)
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT id FROM exchanges WHERE session_id = ?", (sid,)
            ).fetchone()
            conn.close()
            update_exchange_review(
                row[0], "corrected", corrected_risk_level="HIGH",
                corrected_care_level="emergency",
                review_reason="Pattern escalation", db_path=db_path,
            )

    def test_detects_pattern_from_corrections(self, db_path):
        self._setup_corrected_exchanges(
            db_path, ["headache", "blurry vision"], 3,
        )
        patterns = detect_combination_patterns(db_path)
        assert len(patterns) >= 1
        found = False
        for p in patterns:
            if set(p["flags"]) == {"headache", "blurry vision"}:
                found = True
                assert p["occurrences"] >= 3
                assert p["proposed_level"] == "HIGH"
        assert found

    def test_ignores_single_flag_corrections(self, db_path):
        # Single-flag corrections should not produce combination patterns
        for i in range(4):
            sid = f"single_{i}"
            save_session(
                session_id=sid, intake_answers=None, highest_risk="LOW",
                highest_care_level="self_care", message_count=1,
                session_symptoms=[], db_path=db_path,
            )
            save_exchange(
                session_id=sid, exchange_index=0,
                user_input="test", assistant_response="reply",
                local_risk_level="LOW", local_risk_flags=["headache"],
                gpt_risk_level="LOW", gpt_risk_flags=[],
                merged_risk_level="LOW", care_level="self_care",
                follow_up_questions=[], evaluation=None, tree_matches=[],
                db_path=db_path,
            )
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT id FROM exchanges WHERE session_id = ?", (sid,)
            ).fetchone()
            conn.close()
            update_exchange_review(
                row[0], "corrected", corrected_risk_level="HIGH",
                db_path=db_path,
            )
        patterns = detect_combination_patterns(db_path)
        assert len(patterns) == 0

    def test_respects_min_occurrences(self, db_path):
        self._setup_corrected_exchanges(
            db_path, ["headache", "dizziness"], 2,
        )
        patterns = detect_combination_patterns(db_path, min_occurrences=3)
        assert len(patterns) == 0

    def test_returns_empty_when_no_corrections(self, db_path):
        patterns = detect_combination_patterns(db_path)
        assert patterns == []


class TestGenerateProposals:
    def _setup_corrected_exchanges(self, db_path, flag_combo, count, session_prefix="gen"):
        """Helper to insert sessions and corrected exchanges."""
        for i in range(count):
            sid = f"{session_prefix}_{i}"
            save_session(
                session_id=sid, intake_answers=None, highest_risk="LOW",
                highest_care_level="self_care", message_count=1,
                session_symptoms=[], db_path=db_path,
            )
            save_exchange(
                session_id=sid, exchange_index=0,
                user_input="test", assistant_response="reply",
                local_risk_level="LOW", local_risk_flags=flag_combo[:1],
                gpt_risk_level="LOW", gpt_risk_flags=flag_combo[1:],
                merged_risk_level="LOW", care_level="self_care",
                follow_up_questions=[], evaluation=None, tree_matches=[],
                db_path=db_path,
            )
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT id FROM exchanges WHERE session_id = ?", (sid,)
            ).fetchone()
            conn.close()
            update_exchange_review(
                row[0], "corrected", corrected_risk_level="HIGH",
                db_path=db_path,
            )

    def test_generates_new_rule_proposals(self, db_env):
        db_path, classifier_path = db_env
        self._setup_corrected_exchanges(db_path, ["nausea", "dizziness"], 3)
        result = generate_proposals(db_path, classifier_path)
        assert len(result["new_proposals"]) >= 1
        pending = get_pending_rule_proposals(db_path)
        assert len(pending) >= 1

    def test_does_not_duplicate_existing_proposals(self, db_env):
        db_path, classifier_path = db_env
        self._setup_corrected_exchanges(db_path, ["nausea", "dizziness"], 3)
        generate_proposals(db_path, classifier_path)
        first_count = len(get_pending_rule_proposals(db_path))
        generate_proposals(db_path, classifier_path)
        second_count = len(get_pending_rule_proposals(db_path))
        assert second_count == first_count
