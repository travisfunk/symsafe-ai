import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from symsafe.web.app import create_app, build_maps_link, _sessions


@pytest.fixture
def app():
    """Create a test Flask app with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test.db"
        with patch("symsafe.web.app.init_db") as mock_init, \
             patch("symsafe.web.app.load_combination_rules_from_db"), \
             patch("symsafe.web.app.generate_proposals"), \
             patch("symsafe.web.app.get_client") as mock_client_factory, \
             patch("symsafe.web.app.load_base_prompt", return_value="You are a triage assistant."):
            mock_client = MagicMock()
            mock_client_factory.return_value = mock_client
            application = create_app(test_config={"TESTING": True})
            application._test_mock_client = mock_client
            yield application
            _sessions.clear()


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


class TestFlaskApp:
    def test_app_creates(self, app):
        from flask import Flask
        assert isinstance(app, Flask)

    def test_index_returns_200(self, client):
        rv = client.get("/")
        assert rv.status_code == 200

    def test_index_contains_symsafe(self, client):
        rv = client.get("/")
        assert b"SymSafe" in rv.data

    def test_chat_requires_json(self, client):
        rv = client.post("/api/chat", data="not json")
        assert rv.status_code == 400

    def test_chat_requires_message(self, client):
        rv = client.post("/api/chat",
                         data=json.dumps({}),
                         content_type="application/json")
        data = rv.get_json()
        assert "error" in data

    def test_intake_accepts_json(self, client):
        rv = client.post("/api/intake",
                         data=json.dumps({
                             "session_id": "test_session",
                             "answers": {"concern": "Pain"},
                             "zip_code": "46038"
                         }),
                         content_type="application/json")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["status"] == "ok"

    def test_end_session_works(self, client):
        rv = client.post("/api/end-session",
                         data=json.dumps({}),
                         content_type="application/json")
        data = rv.get_json()
        assert "summary" in data


class TestMapsLink:
    def test_maps_link_with_zip(self):
        link = build_maps_link("urgent_care", "46038")
        assert "near+46038" in link

    def test_maps_link_without_zip(self):
        link = build_maps_link("urgent_care")
        assert "near+me" in link

    def test_maps_link_emergency(self):
        link = build_maps_link("emergency", "90210")
        assert "emergency+room" in link

    def test_maps_link_urgent_care(self):
        link = build_maps_link("urgent_care", "90210")
        assert "urgent+care" in link
