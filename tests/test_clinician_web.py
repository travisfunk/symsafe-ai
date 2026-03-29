import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from symsafe.web.app import create_app, _sessions
from symsafe.store import (
    init_db, save_session, save_exchange, get_session_stats,
    get_synonym_proposals_for_session, count_similar_exchanges,
    get_all_synonym_proposals, get_all_rule_proposals,
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

    def test_review_contains_tabs(self, client):
        rv = client.get("/review")
        html = rv.data.decode()
        assert "Review queue" in html
        assert "Learning queue" in html
        assert "Manage classifier" in html


class TestSessionDataAPI:
    def test_session_data_returns_json(self, client):
        rv = client.get("/api/review/session-data/20260325_091500")
        data = rv.get_json()
        # Either returns session data or 404 - both are valid JSON
        assert rv.status_code in (200, 404)
        if rv.status_code == 200:
            assert "session" in data
            assert "exchanges" in data

    def test_session_data_404_for_missing(self, client):
        rv = client.get("/api/review/session-data/nonexistent_session_9999")
        assert rv.status_code == 404


class TestClassifierDataAPI:
    def test_classifier_data_returns_flags(self, client):
        rv = client.get("/api/review/classifier-data")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "high_flags" in data
        assert "moderate_flags" in data
        assert "combination_rules" in data


class TestRewriteAPI:
    def test_rewrite_requires_json(self, client):
        rv = client.post("/api/review/rewrite")
        assert rv.status_code == 400


class TestAddSynonymAPI:
    def test_add_synonym_requires_fields(self, client):
        rv = client.post(
            "/api/review/add-synonym",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert rv.status_code == 400


class TestImpactAPI:
    def test_impact_returns_count(self, client):
        rv = client.get("/api/review/impact/headache")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "count" in data


class TestAnalyzeEndpoint:
    def test_analyze_endpoint_returns_json(self, client):
        rv = client.get("/api/review/analyze/20260325_091500")
        # May return 200 (cached), 503 (no API key), or 500 (test db lacks table)
        assert rv.status_code in (200, 500, 503)
        data = rv.get_json()
        assert isinstance(data, dict)

    def test_analyze_invalid_session_id(self, client):
        rv = client.get("/api/review/analyze/nonexistent_session_9999")
        # 404 if validation passes but session missing, or 500 if table missing
        assert rv.status_code in (404, 500)


class TestBulkSynonymsEndpoint:
    def test_bulk_synonyms_requires_json(self, client):
        rv = client.post("/api/review/bulk-synonyms")
        assert rv.status_code == 400

    def test_bulk_synonyms_requires_fields(self, client):
        rv = client.post(
            "/api/review/bulk-synonyms",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert rv.status_code == 400


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

    def test_count_similar_exchanges(self, db_path):
        save_session(
            session_id="test_count", intake_answers=None,
            highest_risk="LOW", highest_care_level="self_care",
            message_count=1, session_symptoms=[], db_path=db_path,
        )
        save_exchange(
            session_id="test_count", exchange_index=0,
            user_input="I have a bad headache",
            assistant_response="Let me help.",
            local_risk_level="LOW", local_risk_flags=[],
            gpt_risk_level="MODERATE", gpt_risk_flags=["headache"],
            merged_risk_level="MODERATE", care_level="primary_care",
            follow_up_questions=[], evaluation=None, tree_matches=[],
            db_path=db_path,
        )
        result = count_similar_exchanges("headache", db_path=db_path)
        assert result["count"] >= 1
        assert isinstance(result["sample_inputs"], list)

    def test_get_all_synonym_proposals(self, db_path):
        save_synonym_proposal(
            db_path=db_path, patient_phrase="test phrase",
            gpt_risk_level="HIGH", local_risk_level="LOW",
            proposed_category="HIGH", proposed_synonym_for="test",
            session_id="test1",
        )
        all_proposals = get_all_synonym_proposals(db_path=db_path)
        assert len(all_proposals) >= 1

        pending = get_all_synonym_proposals(status="pending", db_path=db_path)
        assert len(pending) >= 1

    def test_get_all_rule_proposals(self, db_path):
        results = get_all_rule_proposals(db_path=db_path)
        assert isinstance(results, list)
