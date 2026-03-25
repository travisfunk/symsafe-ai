import pytest
import tempfile
from pathlib import Path
from symsafe.report import generate_report, save_report


class TestGenerateReport:
    def _sample_data(self):
        return {
            "timestamp": "20260324_154700",
            "intake_answers": {
                "concern": "Pain",
                "location": "Chest",
                "onset": "Today",
                "severity": "7",
                "trajectory": "Getting worse",
                "medications": "Aspirin",
                "conditions": "Heart disease"
            },
            "session_symptoms": ["chest pain", "shortness of breath", "dizziness"],
            "highest_risk": "HIGH",
            "highest_care_level": "emergency",
            "message_count": 4,
            "conversation_log": [
                {
                    "user": "I've had chest pain since last night.",
                    "assistant": "I want to make sure we take this seriously.",
                    "risk": "🔴 HIGH RISK",
                    "care_level": "emergency",
                    "risk_flags": ["chest pain"]
                },
                {
                    "user": "I'm also having trouble breathing.",
                    "assistant": "That's very concerning combined with chest pain.",
                    "risk": "🔴 HIGH RISK",
                    "care_level": "emergency",
                    "risk_flags": ["shortness of breath"]
                }
            ],
            "follow_up_questions": [
                "When did the chest pain start?",
                "Is the pain constant or does it come and go?"
            ]
        }

    def test_returns_string(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert isinstance(html, str)

    def test_contains_html_structure(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()
        assert "<html" in html
        assert "</html>" in html
        assert "<head" in html
        assert "<body" in html

    def test_contains_report_title(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "SymSafe" in html or "SYMSAFE" in html or "Triage Report" in html

    def test_contains_symptoms(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "chest pain" in html.lower()
        assert "shortness of breath" in html.lower()

    def test_contains_risk_level(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "HIGH" in html

    def test_contains_care_guidance(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "911" in html or "emergency" in html.lower()

    def test_contains_intake_data(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "Pain" in html
        assert "Chest" in html
        assert "Aspirin" in html

    def test_contains_conversation_entries(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "chest pain since last night" in html.lower()

    def test_contains_follow_up_questions(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "When did the chest pain start?" in html

    def test_contains_disclaimer(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "not a medical diagnosis" in html.lower() or "not a diagnosis" in html.lower()

    def test_contains_print_styles(self):
        data = self._sample_data()
        html = generate_report(**data)
        assert "@media print" in html

    def test_no_intake_data(self):
        data = self._sample_data()
        data["intake_answers"] = None
        html = generate_report(**data)
        assert isinstance(html, str)
        assert "HIGH" in html

    def test_empty_follow_ups(self):
        data = self._sample_data()
        data["follow_up_questions"] = []
        html = generate_report(**data)
        assert isinstance(html, str)

    def test_low_risk_report(self):
        data = self._sample_data()
        data["highest_risk"] = "LOW"
        data["highest_care_level"] = "self_care"
        data["session_symptoms"] = ["mild headache"]
        html = generate_report(**data)
        assert "LOW" in html


class TestSaveReport:
    def test_saves_file(self):
        html = "<html><body>Test</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report(html, Path(tmpdir), "20260324_154700")
            assert path.exists()
            assert path.name == "symsafe_report_20260324_154700.html"

    def test_file_contains_content(self):
        html = "<html><body>Test report content</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report(html, Path(tmpdir), "test_timestamp")
            content = path.read_text(encoding="utf-8")
            assert "Test report content" in content

    def test_creates_directory(self):
        html = "<html><body>Test</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_subdir"
            path = save_report(html, new_dir, "test_timestamp")
            assert new_dir.exists()
            assert path.exists()

    def test_returns_path_object(self):
        html = "<html><body>Test</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report(html, Path(tmpdir), "test_timestamp")
            assert isinstance(path, Path)


class TestReportInMain:
    def test_main_imports_report(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "report" in content, "main.py should import from report module"

    def test_main_tracks_conversation_log(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "conversation_log" in content, "main.py should collect conversation_log"

    def test_main_calls_generate_report(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "generate_report" in content, "main.py should call generate_report"

    def test_main_saves_report(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "save_report" in content, "main.py should call save_report"

    def test_main_has_report_message(self):
        path = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
        content = path.read_text(encoding="utf-8")
        assert "report saved" in content.lower() or "patient report" in content.lower(), \
            "main.py should tell user where the report was saved"

    def test_gitignore_has_reports(self):
        path = Path(__file__).resolve().parent.parent / ".gitignore"
        content = path.read_text()
        assert "reports" in content, ".gitignore should include reports/"
