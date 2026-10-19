"""Regression tests for session isolation, report access, and login hardening.

Covers the issues found in the October 2026 security review:
- predictable (timestamp) session IDs
- chat/end-session trusting a client-supplied session ID
- patient reports served to anyone who knows the filename
- hardcoded fallback Flask secret key
- no brute-force protection on the clinician login
"""
import json
import os
import re
from unittest.mock import MagicMock, patch

import pytest

from symsafe.web.app import create_app, _sessions
from tests.test_security import app, client, auth_app, auth_client  # noqa: F401 (fixtures)


def _mock_chat(app):
    response_json = json.dumps({
        "response": "OK", "risk_level": "LOW",
        "risk_flags": [], "follow_up_questions": [], "care_level": "self_care",
    })
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_json)]
    app._test_mock_client.messages.create.return_value = mock_response


def _intake(c, **extra):
    body = {"answers": {}, "zip_code": None}
    body.update(extra)
    rv = c.post("/api/intake", data=json.dumps(body), content_type="application/json")
    assert rv.status_code == 200
    return rv.get_json()["session_id"]


class TestSessionIds:
    def test_intake_issues_unguessable_id(self, client):
        sid = _intake(client)
        assert re.fullmatch(r"[0-9a-f]{32}", sid)

    def test_intake_ignores_client_chosen_id(self, client):
        sid = _intake(client, session_id="20261019_115000")
        assert sid != "20261019_115000"


class TestSessionIsolation:
    def test_chat_cannot_reach_another_patients_session(self, app):
        _mock_chat(app)
        patient = app.test_client()
        attacker = app.test_client()
        victim_id = _intake(patient)

        with patch("symsafe.web.app.save_exchange"), patch("symsafe.web.app.log_interaction"):
            rv = attacker.post("/api/chat",
                               data=json.dumps({"message": "hello", "session_id": victim_id}),
                               content_type="application/json")
        assert rv.status_code == 200
        assert _sessions[victim_id]["session_message_count"] == 0
        assert _sessions[victim_id]["messages"] == [] or all(
            "hello" not in str(m.get("content", "")) for m in _sessions[victim_id]["messages"]
        )

    def test_end_session_cannot_end_another_patients_session(self, app):
        patient = app.test_client()
        attacker = app.test_client()
        victim_id = _intake(patient)
        rv = attacker.post("/api/end-session",
                           data=json.dumps({"session_id": victim_id}),
                           content_type="application/json")
        assert rv.status_code == 200
        assert rv.get_json()["report_url"] is None
        assert victim_id in _sessions

    def test_rate_limit_not_bypassed_by_changing_session_id(self, app):
        _mock_chat(app)
        c = app.test_client()
        with patch("symsafe.web.app.save_exchange"), patch("symsafe.web.app.log_interaction"):
            for i in range(30):
                rv = c.post("/api/chat",
                            data=json.dumps({"message": f"msg {i}", "session_id": f"fresh{i}"}),
                            content_type="application/json")
                assert rv.status_code == 200
            rv = c.post("/api/chat",
                        data=json.dumps({"message": "one more", "session_id": "fresh_again"}),
                        content_type="application/json")
        assert rv.status_code == 429


class TestReportAccess:
    @pytest.fixture
    def report(self, tmp_path):
        rid = "a" * 32
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / f"symsafe_report_{rid}.html").write_text("<p>patient report</p>")
        with patch("symsafe.web.app.BASE_DIR", tmp_path):
            yield rid

    def test_stranger_cannot_read_report(self, auth_app, report):
        rv = auth_app.test_client().get(f"/reports/symsafe_report_{report}.html")
        assert rv.status_code == 404

    def test_owner_can_read_own_report(self, auth_app, report):
        owner = auth_app.test_client()
        with owner.session_transaction() as sess:
            sess["report_ids"] = [report]
        rv = owner.get(f"/reports/symsafe_report_{report}.html")
        assert rv.status_code == 200
        assert b"patient report" in rv.data

    def test_clinician_can_read_report(self, auth_app, report):
        clinician = auth_app.test_client()
        clinician.post("/review/login", data={"password": "test-pass"})
        rv = clinician.get(f"/reports/symsafe_report_{report}.html")
        assert rv.status_code == 200


class TestSecretKey:
    def test_no_hardcoded_fallback_secret(self):
        env = {k: v for k, v in os.environ.items() if k != "FLASK_SECRET_KEY"}
        env.update({"REVIEW_PASSWORD": "test-pass", "ANTHROPIC_API_KEY": "test-key"})
        with patch("symsafe.web.app.init_db"), \
             patch("symsafe.web.app.load_combination_rules_from_db"), \
             patch("symsafe.web.app.get_client"), \
             patch("symsafe.web.app.load_base_prompt", return_value="Test prompt."), \
             patch.dict("os.environ", env, clear=True):
            a = create_app()
            b = create_app()
        assert a.secret_key != "symsafe-dev-key-change-in-production"
        assert a.secret_key != b.secret_key


class TestLoginLockout:
    def test_locks_out_after_repeated_failures(self, auth_client):
        for _ in range(5):
            rv = auth_client.post("/review/login", data={"password": "wrong"})
            assert rv.status_code == 200
        rv = auth_client.post("/review/login", data={"password": "test-pass"})
        assert rv.status_code == 429
        assert auth_client.get("/review").status_code == 302
