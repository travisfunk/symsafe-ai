import pytest
from pathlib import Path


class TestRepeatEscalation:
    def test_main_tracks_messages_since_escalation(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "messages_since_escalation" in content, \
            "main.py should track messages since last escalation"

    def test_main_has_escalation_warning(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "recommended" in content.lower() and ("ago" in content.lower() or "escalat" in content.lower()), \
            "main.py should warn when patient keeps chatting after escalation"

    def test_main_resets_on_topic_change(self):
        """Escalation tracking should reset when conversation moves to non-clinical"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "messages_since_escalation = 0" in content, \
            "main.py should reset escalation tracking"


class TestCareRoutingInMain:
    def test_main_imports_care_router(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "care_router" in content, "main.py should import from care_router"

    def test_main_displays_care_guidance(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "where" in content.lower() and "right_now" in content.lower(), \
            "main.py should display care guidance with where and right_now fields"

    def test_logger_accepts_care_level(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "logger.py"
        content = path.read_text(encoding="utf-8")
        assert "care_level" in content, "logger.py should accept care_level parameter"
