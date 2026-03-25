import sqlite3
import tempfile
from pathlib import Path

import pytest

from symsafe.store import (
    init_db,
    save_session,
    get_session,
    get_all_sessions,
    save_exchange,
    get_exchanges,
    update_session_status,
    update_exchange_review,
)


@pytest.fixture
def db_path():
    """Provide a temporary database path that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


def _init(db_path):
    init_db(db_path=db_path)


class TestDatabase:
    def test_init_db_creates_tables(self, db_path):
        _init(db_path)
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        for table in ("sessions", "exchanges", "synonym_proposals", "rule_proposals"):
            assert table in tables

    def test_save_and_get_session(self, db_path):
        _init(db_path)
        save_session(
            session_id="20260324_120000",
            intake_answers={"concern": "headache"},
            highest_risk="MODERATE",
            highest_care_level="primary_care",
            message_count=3,
            session_symptoms=["headache", "fever"],
            db_path=db_path,
        )
        session = get_session("20260324_120000", db_path=db_path)
        assert session is not None
        assert session["id"] == "20260324_120000"
        assert session["intake_answers"] == {"concern": "headache"}
        assert session["highest_risk"] == "MODERATE"
        assert session["highest_care_level"] == "primary_care"
        assert session["message_count"] == 3
        assert session["session_symptoms"] == ["headache", "fever"]
        assert session["status"] == "pending_review"

    def test_save_and_get_exchanges(self, db_path):
        _init(db_path)
        save_session(
            session_id="20260324_120000",
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=2,
            session_symptoms=[],
            db_path=db_path,
        )
        for i in range(2):
            save_exchange(
                session_id="20260324_120000",
                exchange_index=i,
                user_input=f"message {i}",
                assistant_response=f"reply {i}",
                local_risk_level="LOW",
                local_risk_flags=[],
                gpt_risk_level="LOW",
                gpt_risk_flags=[],
                merged_risk_level="LOW",
                care_level="self_care",
                follow_up_questions=[],
                evaluation=None,
                tree_matches=[],
                db_path=db_path,
            )
        exchanges = get_exchanges("20260324_120000", db_path=db_path)
        assert len(exchanges) == 2
        assert exchanges[0]["exchange_index"] == 0
        assert exchanges[1]["exchange_index"] == 1

    def test_get_all_sessions_ordered(self, db_path):
        _init(db_path)
        for ts in ("20260321_100000", "20260323_100000", "20260322_100000"):
            save_session(
                session_id=ts,
                intake_answers=None,
                highest_risk="LOW",
                highest_care_level="self_care",
                message_count=1,
                session_symptoms=[],
                db_path=db_path,
            )
        sessions = get_all_sessions(db_path=db_path)
        assert len(sessions) == 3
        timestamps = [s["created_at"] for s in sessions]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_all_sessions_filtered_by_status(self, db_path):
        _init(db_path)
        save_session(
            session_id="20260324_110000",
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=1,
            session_symptoms=[],
            db_path=db_path,
        )
        save_session(
            session_id="20260324_120000",
            intake_answers=None,
            highest_risk="HIGH",
            highest_care_level="emergency",
            message_count=2,
            session_symptoms=["chest pain"],
            db_path=db_path,
        )
        update_session_status("20260324_120000", "reviewed", db_path=db_path)
        pending = get_all_sessions(status="pending_review", db_path=db_path)
        reviewed = get_all_sessions(status="reviewed", db_path=db_path)
        assert len(pending) == 1
        assert pending[0]["id"] == "20260324_110000"
        assert len(reviewed) == 1
        assert reviewed[0]["id"] == "20260324_120000"

    def test_update_session_status(self, db_path):
        _init(db_path)
        save_session(
            session_id="20260324_120000",
            intake_answers=None,
            highest_risk="HIGH",
            highest_care_level="emergency",
            message_count=1,
            session_symptoms=["chest pain"],
            db_path=db_path,
        )
        update_session_status(
            "20260324_120000", "reviewed",
            reviewer_notes="Looks correct", db_path=db_path,
        )
        session = get_session("20260324_120000", db_path=db_path)
        assert session["status"] == "reviewed"
        assert session["reviewer_notes"] == "Looks correct"

    def test_update_exchange_review(self, db_path):
        _init(db_path)
        save_session(
            session_id="20260324_120000",
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=1,
            session_symptoms=[],
            db_path=db_path,
        )
        save_exchange(
            session_id="20260324_120000",
            exchange_index=0,
            user_input="my arm feels weird",
            assistant_response="Can you describe that?",
            local_risk_level="LOW",
            local_risk_flags=[],
            gpt_risk_level="MODERATE",
            gpt_risk_flags=["arm numbness"],
            merged_risk_level="MODERATE",
            care_level="primary_care",
            follow_up_questions=["Is it numb or tingling?"],
            evaluation=None,
            tree_matches=[],
            db_path=db_path,
        )
        exchanges = get_exchanges("20260324_120000", db_path=db_path)
        exchange_id = exchanges[0]["id"]
        update_exchange_review(
            exchange_id,
            review_status="corrected",
            corrected_risk_level="HIGH",
            corrected_care_level="urgent_care",
            review_reason="Arm numbness could indicate stroke",
            db_path=db_path,
        )
        updated = get_exchanges("20260324_120000", db_path=db_path)
        ex = updated[0]
        assert ex["review_status"] == "corrected"
        assert ex["corrected_risk_level"] == "HIGH"
        assert ex["corrected_care_level"] == "urgent_care"
        assert ex["review_reason"] == "Arm numbness could indicate stroke"

    def test_save_session_with_null_intake(self, db_path):
        _init(db_path)
        save_session(
            session_id="20260324_120000",
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=0,
            session_symptoms=[],
            db_path=db_path,
        )
        session = get_session("20260324_120000", db_path=db_path)
        assert session["intake_answers"] is None

    def test_exchanges_foreign_key(self, db_path):
        _init(db_path)
        save_session(
            session_id="session_a",
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=1,
            session_symptoms=[],
            db_path=db_path,
        )
        save_session(
            session_id="session_b",
            intake_answers=None,
            highest_risk="LOW",
            highest_care_level="self_care",
            message_count=1,
            session_symptoms=[],
            db_path=db_path,
        )
        save_exchange(
            session_id="session_a", exchange_index=0,
            user_input="hello", assistant_response="hi",
            local_risk_level="LOW", local_risk_flags=[],
            gpt_risk_level="LOW", gpt_risk_flags=[],
            merged_risk_level="LOW", care_level="self_care",
            follow_up_questions=[], evaluation=None, tree_matches=[],
            db_path=db_path,
        )
        save_exchange(
            session_id="session_b", exchange_index=0,
            user_input="bye", assistant_response="goodbye",
            local_risk_level="LOW", local_risk_flags=[],
            gpt_risk_level="LOW", gpt_risk_flags=[],
            merged_risk_level="LOW", care_level="self_care",
            follow_up_questions=[], evaluation=None, tree_matches=[],
            db_path=db_path,
        )
        a_exchanges = get_exchanges("session_a", db_path=db_path)
        b_exchanges = get_exchanges("session_b", db_path=db_path)
        assert len(a_exchanges) == 1
        assert a_exchanges[0]["user_input"] == "hello"
        assert len(b_exchanges) == 1
        assert b_exchanges[0]["user_input"] == "bye"
