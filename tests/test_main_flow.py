import pytest
from pathlib import Path


class TestEvaluationSkipping:
    def test_main_has_evaluation_skip_logic(self):
        """main.py should conditionally skip evaluation for non-clinical messages"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "evaluation = None" in content or "evaluation=None" in content, \
            "main.py should set evaluation to None when skipping"

    def test_main_does_not_print_evaluation(self):
        """main.py should NOT have print_evaluation function or call"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "print_evaluation" not in content, \
            "main.py should not have print_evaluation — evaluation is logged only, not shown to patient"

    def test_main_has_patient_friendly_high_risk_message(self):
        """main.py should show a patient-friendly warning for HIGH risk"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "911" in content or "emergency" in content.lower(), \
            "main.py should show emergency guidance for HIGH risk"

    def test_main_has_patient_friendly_moderate_risk_message(self):
        """main.py should show a patient-friendly note for MODERATE risk"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "appointment" in content.lower() or "healthcare provider" in content.lower(), \
            "main.py should suggest seeing a doctor for MODERATE risk"


class TestLoggerHandlesNone:
    def test_logger_handles_none_evaluation(self):
        """logger.py should handle evaluation=None gracefully"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "logger.py"
        content = path.read_text(encoding="utf-8")
        assert "None" in content or "none" in content or "Skipped" in content, \
            "logger.py should handle None evaluation (skipped for non-clinical)"

    def test_logger_log_interaction_accepts_none(self):
        """Verify log_interaction can be called with evaluation=None without crashing"""
        import tempfile
        from symsafe.logger import create_log_file, log_interaction
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = create_log_file(Path(tmpdir), "test_timestamp")
            # This should not raise an exception
            log_interaction(
                log_filename=log_path,
                user_input="Hello there",
                risk_level="🟢 LOW RISK",
                risk_flags=[],
                reply="Hi! How can I help?",
                evaluation=None,
                tree_matches=[]
            )
            content = log_path.read_text(encoding="utf-8")
            assert "Skipped" in content or "non-clinical" in content.lower()


class TestEvaluatorModel:
    def test_evaluator_uses_haiku(self):
        """evaluator.py should reference claude-haiku, not the main model"""
        path = Path(__file__).resolve().parent.parent / "symsafe" / "evaluator.py"
        content = path.read_text(encoding="utf-8")
        assert "claude-haiku-4-5-20251001" in content, "evaluator.py should use claude-haiku-4-5-20251001"
        lines_with_model = [l for l in content.split('\n') if 'model=' in l and 'claude' in l]
        for line in lines_with_model:
            assert "haiku" in line, f"Found non-haiku model reference: {line.strip()}"
