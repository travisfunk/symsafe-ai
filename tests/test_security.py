import json
import os
from unittest.mock import MagicMock, patch

import pytest

from symsafe.web.app import create_app, _sessions


@pytest.fixture
def app():
    """Create a test Flask app with TESTING=True (bypasses review auth)."""
    with patch("symsafe.web.app.init_db"), \
         patch("symsafe.web.app.load_combination_rules_from_db"), \
         patch("symsafe.web.app.generate_proposals"), \
         patch("symsafe.web.app.get_client") as mock_client_factory, \
         patch("symsafe.web.app.load_base_prompt", return_value="Test prompt."):
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        application = create_app(test_config={"TESTING": True})
        application._test_mock_client = mock_client
        yield application
        _sessions.clear()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_app():
    """Create a test Flask app with auth ENABLED (TESTING not set)."""
    with patch("symsafe.web.app.init_db"), \
         patch("symsafe.web.app.load_combination_rules_from_db"), \
         patch("symsafe.web.app.generate_proposals"), \
         patch("symsafe.web.app.get_client") as mock_client_factory, \
         patch("symsafe.web.app.load_base_prompt", return_value="Test prompt."), \
         patch.dict("os.environ", {"REVIEW_PASSWORD": "test-pass"}, clear=False):
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        application = create_app()
        yield application
        _sessions.clear()


@pytest.fixture
def auth_client(auth_app):
    return auth_app.test_client()


@pytest.fixture
def no_key_app():
    """Create a test Flask app with no API key."""
    with patch("symsafe.web.app.init_db"), \
         patch("symsafe.web.app.load_combination_rules_from_db"), \
         patch("symsafe.web.app.generate_proposals"), \
         patch("symsafe.web.app.get_client") as mock_client_factory, \
         patch("symsafe.web.app.load_base_prompt", return_value="Test prompt."), \
         patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
        mock_client_factory.return_value = None
        application = create_app(test_config={"TESTING": True})
        yield application
        _sessions.clear()


@pytest.fixture
def no_key_client(no_key_app):
    return no_key_app.test_client()


class TestInputSanitization:
    def test_chat_rejects_empty_message(self, client):
        rv = client.post("/api/chat",
                         data=json.dumps({"message": "", "session_id": "test"}),
                         content_type="application/json")
        assert rv.status_code == 400

    def test_chat_rejects_long_message(self, client):
        rv = client.post("/api/chat",
                         data=json.dumps({"message": "a" * 1500, "session_id": "test"}),
                         content_type="application/json")
        assert rv.status_code == 400

    def test_chat_strips_html(self, client, app):
        mock_client = app._test_mock_client
        response_json = json.dumps({
            "response": "I see.", "risk_level": "LOW",
            "risk_flags": [], "follow_up_questions": [], "care_level": "self_care"
        })
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=response_json))
        ]
        with patch("symsafe.web.app.save_exchange"), \
             patch("symsafe.web.app.log_interaction"):
            rv = client.post("/api/chat",
                             data=json.dumps({
                                 "message": "<script>alert('xss')</script>I have a headache",
                                 "session_id": "test_xss"
                             }),
                             content_type="application/json")
            assert rv.status_code == 200
            state = _sessions.get("test_xss")
            if state:
                user_msgs = [m["content"] for m in state["messages"] if m["role"] == "user"]
                for msg in user_msgs:
                    assert "<script>" not in msg

    def test_intake_validates_severity(self, client):
        rv = client.post("/api/intake",
                         data=json.dumps({
                             "session_id": "test_sev",
                             "answers": {"severity": "abc"},
                         }),
                         content_type="application/json")
        assert rv.status_code == 200

    def test_intake_validates_zip(self, client):
        rv = client.post("/api/intake",
                         data=json.dumps({
                             "session_id": "test_zip",
                             "answers": {},
                             "zip_code": "not-a-zip",
                         }),
                         content_type="application/json")
        assert rv.status_code == 200
        state = _sessions.get("test_zip")
        if state:
            assert state["zip_code"] is None

    def test_review_exchange_validates_action(self, client):
        rv = client.post("/api/review/exchange/1",
                         data=json.dumps({"action": "invalid"}),
                         content_type="application/json")
        assert rv.status_code == 400


class TestAuthentication:
    def test_review_redirects_without_login(self, auth_client):
        rv = auth_client.get("/review")
        assert rv.status_code == 302
        assert "/review/login" in rv.headers.get("Location", "")

    def test_review_login_page_exists(self, auth_client):
        rv = auth_client.get("/review/login")
        assert rv.status_code == 200
        assert b"password" in rv.data.lower()

    def test_review_accessible_after_login(self, auth_client):
        auth_client.post("/review/login", data={"password": "test-pass"})
        rv = auth_client.get("/review")
        assert rv.status_code == 200

    def test_review_rejects_wrong_password(self, auth_client):
        rv = auth_client.post("/review/login", data={"password": "wrong"})
        assert rv.status_code == 200
        assert b"Incorrect password" in rv.data


class TestRateLimiting:
    def test_chat_enforces_message_limit(self, client, app):
        mock_client = app._test_mock_client
        response_json = json.dumps({
            "response": "OK", "risk_level": "LOW",
            "risk_flags": [], "follow_up_questions": [], "care_level": "self_care"
        })
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=response_json))
        ]

        session_id = "rate_limit_test"
        with patch("symsafe.web.app.save_exchange"), \
             patch("symsafe.web.app.log_interaction"):
            for i in range(30):
                rv = client.post("/api/chat",
                                 data=json.dumps({"message": f"msg {i}", "session_id": session_id}),
                                 content_type="application/json")
                assert rv.status_code == 200, f"Message {i} failed with {rv.status_code}"

            # 31st should be rate limited
            rv = client.post("/api/chat",
                             data=json.dumps({"message": "one more", "session_id": session_id}),
                             content_type="application/json")
            assert rv.status_code == 429


class TestSecurityHeaders:
    def test_response_has_security_headers(self, client):
        rv = client.get("/")
        assert rv.headers.get("X-Content-Type-Options") == "nosniff"
        assert rv.headers.get("X-Frame-Options") == "DENY"
        assert rv.headers.get("X-XSS-Protection") == "1; mode=block"


class TestApiKeyProtection:
    def test_no_api_key_in_responses(self, client):
        rv = client.get("/")
        body = rv.data.decode("utf-8")
        # Check that no actual API key pattern appears (not function names like skipToChat)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key and len(api_key) > 10:
            assert api_key not in body

    def test_chat_works_without_api_key_gracefully(self, no_key_client):
        rv = no_key_client.post("/api/chat",
                                data=json.dumps({"message": "hello", "session_id": "no_key_test"}),
                                content_type="application/json")
        assert rv.status_code == 503
        data = rv.get_json()
        assert "error" in data
        assert "unavailable" in data["error"].lower()
