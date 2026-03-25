import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestProjectDocs:
    def test_readme_exists(self):
        assert (PROJECT_ROOT / "README.md").exists()

    def test_readme_substantial(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert len(content) > 1000, f"README.md is only {len(content)} chars — expected > 1000"

    def test_readme_mentions_all_modules(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        modules = [
            "agent.py", "care_router.py", "intake.py", "report.py",
            "risk_classifier.py", "evaluator.py", "symptom_tree.py",
            "logger.py", "config.py", "main.py"
        ]
        for mod in modules:
            assert mod in content, f"README.md does not mention {mod}"

    def test_readme_mentions_key_features(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "intake" in content, "README should mention intake"
        assert "care routing" in content or "care_router" in content, "README should mention care routing"
        assert "report" in content, "README should mention report"

    def test_readme_has_quick_start(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "pip install" in content, "README should have pip install in quick start"
        assert "python -m symsafe.main" in content, "README should have python -m symsafe.main"

    def test_readme_has_disclaimer(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "prototype" in content, "README should mention prototype"
        assert "not intended for real patient" in content or "not for real patient" in content or "not intended for real clinical" in content, \
            "README should say not for real patients"

    def test_readme_has_testing_section(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "pytest" in content, "README should mention pytest"

    def test_readme_no_old_references(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "symptom_screener.py" not in content, "README should not reference old symptom_screener.py"
        assert "symtom_tree" not in content, "README should not reference old typo symtom_tree"

    def test_env_example_exists(self):
        assert (PROJECT_ROOT / ".env.example").exists(), ".env.example not found"

    def test_env_example_has_placeholder(self):
        content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" in content, ".env.example should contain OPENAI_API_KEY"

    def test_eval_template_not_empty(self):
        content = (PROJECT_ROOT / "evaluations" / "eval_template.md").read_text(encoding="utf-8")
        assert len(content) > 200, "eval_template.md is too short"
        assert "Checklist" in content or "checklist" in content or "Criteria" in content, \
            "eval_template.md should contain evaluation checklist or criteria"

    def test_product_notes_not_empty(self):
        content = (PROJECT_ROOT / "notes" / "product_notes.md").read_text(encoding="utf-8")
        assert len(content) > 200, "product_notes.md is too short"
        assert "Design" in content or "design" in content or "Vision" in content, \
            "product_notes.md should contain design or vision content"

    def test_requirements_has_all_deps(self):
        content = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "openai" in content, "requirements.txt missing openai"
        assert "python-dotenv" in content or "dotenv" in content, "requirements.txt missing python-dotenv"
        assert "pytest" in content, "requirements.txt missing pytest"

    def test_gitignore_is_complete(self):
        content = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in content, ".gitignore missing .env"
        assert "__pycache__" in content, ".gitignore missing __pycache__"
        assert "logs/" in content, ".gitignore missing logs/"
        assert "reports/" in content, ".gitignore missing reports/"
        assert ".pytest_cache" in content, ".gitignore missing .pytest_cache"
