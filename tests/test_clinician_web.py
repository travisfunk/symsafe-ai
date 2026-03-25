import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from symsafe.web.app import create_app, _sessions
from symsafe.store import (
    init_db, save_session, save_exchange, get_session_stats,
    get_synonym_proposals_for_session,
)
from symsafe.feedback import save_synonym_proposal, save_rule_proposal


@pytest.fixture
def app():
    """Create a test Flask app with mocked startup dependencies."""
    with patch("symsafe.web.app.init_db"), \
         patch("symsafe.web.app.load_combination_rules_from_db"), \
         patch("symsafe.web.app.generate_proposals"), \
         patch("symsafe.web.app.get_client") as mock_client_factory, \
         patch("symsafe.web.app.load_base_prompt", return_value="You are a triage assistant."):
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        application = create_app(test_config={"TESTING": True})
        yield application
        _sessions.clear()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def db_path():
    """Provide a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        init_db(db_path=path)
        yield path


class TestClinicianDashboard:
    def test_review_page_returns_200(self, client):
        rv = client.get("/review")
        assert rv.status_code == 200

    def test_review_page_contains_title(self, client):
        rv = client.get("/review")
        assert b"clinician review" in rv.data.lower()

    def test_session_detail_returns_200_or_404(self, client):
        rv = client.get("/review/session/nonexistent")
        assert rv.status_code in (200, 404)


class TestExchangeReview:
    def test_accept_exchange(self, client):
        rv = client.post(
            "/api/review/exchange/1",
            data=json.dumps({"action": "accepted"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"

    def test_correct_exchange(self, client):
        rv = client.post(
            "/api/review/exchange/1",
            data=json.dumps({
                "action": "corrected",
                "corrected_risk_level": "HIGH",
                "corrected_care_level": "emergency",
                "reason": "missed cardiac risk",
            }),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"

    def test_reject_exchange(self, client):
        rv = client.post(
            "/api/review/exchange/1",
            data=json.dumps({
                "action": "rejected",
                "reason": "response was unsafe",
            }),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"


class TestSessionReview:
    def test_mark_reviewed(self, client):
        rv = client.post(
            "/api/review/session/test_id",
            data=json.dumps({"status": "reviewed", "notes": "Looks good"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"

    def test_flag_session(self, client):
        rv = client.post(
            "/api/review/session/test_id",
            data=json.dumps({"status": "flagged", "notes": "Needs follow-up"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"


class TestProposalReview:
    def test_get_pending_proposals(self, client):
        rv = client.get("/api/review/proposals")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "synonyms" in data
        assert "rules" in data

    def test_approve_synonym_proposal(self, client):
        rv = client.post(
            "/api/review/synonym/1",
            data=json.dumps({"action": "approve"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"

    def test_reject_synonym_proposal(self, client):
        rv = client.post(
            "/api/review/synonym/1",
            data=json.dumps({"action": "reject"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"

    def test_approve_rule_proposal(self, client):
        rv = client.post(
            "/api/review/rule/1",
            data=json.dumps({"action": "approve"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"


class TestStoreHelpers:
    def test_get_session_stats_returns_dict(self, db_path):
        stats = get_session_stats(db_path=db_path)
        assert isinstance(stats, dict)
        assert "total_sessions" in stats
        assert "high_risk_count" in stats
        assert "pending_count" in stats
        assert "reviewed_count" in stats

    def test_get_synonym_proposals_for_session(self, db_path):
        save_synonym_proposal(
            db_path=db_path,
            patient_phrase="my chest is burning",
            gpt_risk_level="HIGH",
            local_risk_level="LOW",
            proposed_category="HIGH",
            proposed_synonym_for="chest pain",
            session_id="test1",
        )
        results_test1 = get_synonym_proposals_for_session("test1", db_path=db_path)
        assert len(results_test1) == 1
        assert results_test1[0]["patient_phrase"] == "my chest is burning"

        results_test2 = get_synonym_proposals_for_session("test2", db_path=db_path)
        assert len(results_test2) == 0
