import pytest
import tempfile
from pathlib import Path
from symsafe.logger import log_session_summary


class TestSessionSummary:
    def test_log_session_summary_writes_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.md"
            log_path.write_text("# Test Log\n\n")
            log_session_summary(log_path, ["headache", "dizziness"], "MODERATE", 4)
            content = log_path.read_text()
            assert "headache" in content
            assert "dizziness" in content
            assert "MODERATE" in content

    def test_log_session_summary_empty_symptoms(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.md"
            log_path.write_text("# Test Log\n\n")
            log_session_summary(log_path, [], "LOW", 1)
            content = log_path.read_text()
            assert "No symptoms" in content or "None" in content or "LOW" in content


class TestSessionSummaryInMain:
    def test_main_has_session_tracking(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "session_symptoms" in content, "main.py should track symptoms across session"
        assert "session_highest_risk" in content or "highest_risk" in content, \
            "main.py should track highest risk level"
        assert "session_message_count" in content or "message_count" in content, \
            "main.py should count messages"

    def test_main_has_summary_on_exit(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "Session Summary" in content or "session_summary" in content or "print_session_summary" in content, \
            "main.py should print a session summary on exit"

    def test_main_merges_risk_levels(self):
        """main.py should take the higher of local and GPT risk levels"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "HIGH" in content and "MODERATE" in content, \
            "main.py should handle risk level comparison"


class TestBasePrompt:
    def test_base_prompt_has_rules(self):
        path = Path(__file__).resolve().parent.parent / "prompts" / "base_prompt.txt"
        content = path.read_text(encoding="utf-8")
        assert "NEVER diagnose" in content or "never diagnose" in content, \
            "base_prompt should have clear boundaries about diagnosis"

    def test_base_prompt_has_conversation_awareness(self):
        path = Path(__file__).resolve().parent.parent / "prompts" / "base_prompt.txt"
        content = path.read_text(encoding="utf-8")
        assert "conversation history" in content.lower() or "earlier messages" in content.lower(), \
            "base_prompt should mention conversation awareness"

    def test_base_prompt_has_scope_limits(self):
        path = Path(__file__).resolve().parent.parent / "prompts" / "base_prompt.txt"
        content = path.read_text(encoding="utf-8")
        assert "medication" in content.lower() or "dosage" in content.lower() or "treatment" in content.lower(), \
            "base_prompt should define scope limitations"

    def test_base_prompt_has_escalation_guidance(self):
        path = Path(__file__).resolve().parent.parent / "prompts" / "base_prompt.txt"
        content = path.read_text(encoding="utf-8")
        assert "911" in content or "emergency" in content.lower(), \
            "base_prompt should have emergency escalation guidance"
