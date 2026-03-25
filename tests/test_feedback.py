import tempfile
from pathlib import Path

import pytest

from symsafe.feedback import (
    detect_classifier_gap,
    find_nearest_flag,
    save_synonym_proposal,
    get_pending_proposals,
    approve_synonym,
    reject_proposal,
)
from symsafe.store import init_db
from symsafe.risk_classifier import HIGH_RISK_FLAGS, MODERATE_RISK_FLAGS


@pytest.fixture
def db_path():
    """Provide a temporary database path that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        init_db(db_path=path)
        yield path


class TestGapDetection:
    def test_detects_gap_when_gpt_high_local_low(self):
        gap = detect_classifier_gap(
            "my chest is burning",
            "LOW", [],
            "HIGH", ["chest burning"],
        )
        assert gap is not None
        assert gap["gpt_risk_level"] == "HIGH"
        assert gap["local_risk_level"] == "LOW"

    def test_no_gap_when_both_agree(self):
        gap = detect_classifier_gap(
            "chest pain",
            "HIGH", ["chest pain"],
            "HIGH", ["chest pain"],
        )
        assert gap is None

    def test_no_gap_when_local_higher(self):
        gap = detect_classifier_gap(
            "I feel fine",
            "HIGH", ["chest pain"],
            "LOW", [],
        )
        assert gap is None

    def test_no_gap_when_both_low(self):
        gap = detect_classifier_gap(
            "hello",
            "LOW", [],
            "LOW", [],
        )
        assert gap is None

    def test_gap_includes_patient_phrase(self):
        gap = detect_classifier_gap(
            "my chest is on fire",
            "LOW", [],
            "HIGH", ["chest burning"],
        )
        assert gap["patient_phrase"] == "my chest is on fire"

    def test_gap_includes_gpt_flags(self):
        gap = detect_classifier_gap(
            "my chest is on fire",
            "LOW", [],
            "HIGH", ["chest burning", "possible cardiac"],
        )
        assert "chest burning" in gap["gpt_flags"]
        assert "possible cardiac" in gap["gpt_flags"]


class TestFindNearestFlag:
    def test_finds_exact_substring(self):
        result = find_nearest_flag("chest is burning", HIGH_RISK_FLAGS)
        assert result is not None
        assert "chest" in result.lower()

    def test_returns_none_for_no_overlap(self):
        result = find_nearest_flag("my elbow hurts", HIGH_RISK_FLAGS)
        assert result is None

    def test_finds_best_match(self):
        flags = ["chest pain", "chest tightness", "vision loss"]
        result = find_nearest_flag("chest pain getting worse", flags)
        assert result == "chest pain"


class TestProposalWorkflow:
    def test_save_and_retrieve_synonym_proposal(self, db_path):
        save_synonym_proposal(
            db_path=db_path,
            patient_phrase="my chest is burning",
            gpt_risk_level="HIGH",
            local_risk_level="LOW",
            proposed_category="HIGH",
            proposed_synonym_for="chest pain",
            session_id="20260324_120000",
        )
        proposals = get_pending_proposals(db_path)
        assert len(proposals) == 1
        assert proposals[0]["patient_phrase"] == "my chest is burning"

    def test_approve_proposal(self, db_path):
        save_synonym_proposal(
            db_path=db_path,
            patient_phrase="my chest is burning",
            gpt_risk_level="HIGH",
            local_risk_level="LOW",
            proposed_category="HIGH",
            proposed_synonym_for="chest pain",
            session_id="20260324_120000",
        )
        proposals = get_pending_proposals(db_path)
        approve_synonym(db_path, proposals[0]["id"])
        proposals = get_pending_proposals(db_path)
        # Re-fetch all to check status
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM synonym_proposals WHERE id = 1").fetchone()
        conn.close()
        assert dict(row)["status"] == "approved"

    def test_reject_proposal(self, db_path):
        save_synonym_proposal(
            db_path=db_path,
            patient_phrase="my chest is burning",
            gpt_risk_level="HIGH",
            local_risk_level="LOW",
            proposed_category="HIGH",
            proposed_synonym_for="chest pain",
            session_id="20260324_120000",
        )
        proposals = get_pending_proposals(db_path)
        reject_proposal(db_path, proposals[0]["id"])
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM synonym_proposals WHERE id = 1").fetchone()
        conn.close()
        assert dict(row)["status"] == "rejected"

    def test_approved_not_in_pending(self, db_path):
        save_synonym_proposal(
            db_path=db_path,
            patient_phrase="my chest is burning",
            gpt_risk_level="HIGH",
            local_risk_level="LOW",
            proposed_category="HIGH",
            proposed_synonym_for="chest pain",
            session_id="20260324_120000",
        )
        proposals = get_pending_proposals(db_path)
        approve_synonym(db_path, proposals[0]["id"])
        pending = get_pending_proposals(db_path)
        assert len(pending) == 0
