import pytest
from symsafe.intake import INTAKE_STEPS, format_intake_context


class TestIntakeSteps:
    def test_intake_steps_is_list(self):
        assert isinstance(INTAKE_STEPS, list)

    def test_intake_has_7_steps(self):
        assert len(INTAKE_STEPS) == 7

    def test_all_steps_have_required_fields(self):
        required = {"id", "prompt", "options", "allow_freetext", "help_text"}
        for step in INTAKE_STEPS:
            assert required.issubset(step.keys()), f"Step {step.get('id')} missing fields"

    def test_all_step_ids_unique(self):
        ids = [s["id"] for s in INTAKE_STEPS]
        assert len(ids) == len(set(ids)), "Step IDs must be unique"

    def test_first_step_is_concern(self):
        assert INTAKE_STEPS[0]["id"] == "concern"

    def test_severity_step_has_no_options(self):
        severity = [s for s in INTAKE_STEPS if s["id"] == "severity"][0]
        assert severity["options"] is None

    def test_onset_does_not_allow_freetext(self):
        onset = [s for s in INTAKE_STEPS if s["id"] == "onset"][0]
        assert onset["allow_freetext"] is False


class TestFormatIntakeContext:
    def test_full_answers(self):
        answers = {
            "concern": "Pain",
            "location": "Chest",
            "onset": "Today",
            "severity": "7",
            "trajectory": "Getting worse",
            "medications": "Aspirin",
            "conditions": "Heart disease"
        }
        result = format_intake_context(answers)
        assert "Pain" in result
        assert "Chest" in result
        assert "Today" in result
        assert "7" in result
        assert "Getting worse" in result
        assert "Aspirin" in result
        assert "Heart disease" in result

    def test_partial_answers(self):
        answers = {
            "concern": "Headache",
            "location": "Head"
        }
        result = format_intake_context(answers)
        assert "Headache" in result
        assert "Head" in result

    def test_empty_answers(self):
        result = format_intake_context({})
        assert result == "" or len(result) == 0

    def test_returns_string(self):
        answers = {"concern": "Pain"}
        result = format_intake_context(answers)
        assert isinstance(result, str)

    def test_severity_formatted_with_scale(self):
        answers = {"severity": "7"}
        result = format_intake_context(answers)
        assert "7" in result


class TestIntakeInMain:
    def test_main_imports_intake(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "intake" in content, "main.py should import from intake module"

    def test_main_has_intake_flag(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "--intake" in content, "main.py should support --intake CLI flag"

    def test_main_has_intake_prompt(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "walk you through" in content.lower() or "quick questions" in content.lower(), \
            "main.py should ask if patient wants guided intake"

    def test_intake_module_is_importable(self):
        from symsafe.intake import INTAKE_STEPS, run_intake, format_intake_context
        assert callable(run_intake)
        assert callable(format_intake_context)


class TestIntakeLogging:
    def test_logger_has_log_intake(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "symsafe" / "logger.py"
        content = path.read_text(encoding="utf-8")
        assert "log_intake" in content, "logger.py should have log_intake function"

    def test_log_intake_writes_to_file(self):
        import tempfile
        from pathlib import Path
        from symsafe.logger import create_log_file, log_intake
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = create_log_file(Path(tmpdir), "test_intake")
            answers = {"concern": "Headache", "location": "Head", "severity": "5"}
            log_intake(log_path, answers)
            content = log_path.read_text(encoding="utf-8")
            assert "Headache" in content
            assert "Head" in content
            assert "5" in content

    def test_log_intake_handles_empty(self):
        import tempfile
        from pathlib import Path
        from symsafe.logger import create_log_file, log_intake
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = create_log_file(Path(tmpdir), "test_intake_empty")
            log_intake(log_path, {})
            content = log_path.read_text(encoding="utf-8")
            assert "Intake" in content or "intake" in content
