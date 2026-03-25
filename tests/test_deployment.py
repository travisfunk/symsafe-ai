from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDeploymentConfig:
    def test_render_yaml_exists(self):
        assert (PROJECT_ROOT / "render.yaml").exists()

    def test_render_yaml_has_gunicorn(self):
        content = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
        assert "gunicorn" in content

    def test_render_yaml_references_run_web(self):
        content = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
        assert "run_web" in content

    def test_requirements_has_gunicorn(self):
        content = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "gunicorn" in content

    def test_requirements_has_flask(self):
        content = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "flask" in content

    def test_run_web_exists(self):
        assert (PROJECT_ROOT / "run_web.py").exists()

    def test_run_web_imports_create_app(self):
        content = (PROJECT_ROOT / "run_web.py").read_text(encoding="utf-8")
        assert "create_app" in content

    def test_env_example_has_all_vars(self):
        content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" in content
        assert "FLASK_SECRET_KEY" in content
        assert "REVIEW_PASSWORD" in content


class TestReadmeV3:
    def test_readme_mentions_v3(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "v3.0.0" in content

    def test_readme_mentions_web_ui(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "web" in content
        assert "flask" in content

    def test_readme_mentions_clinician_review(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "clinician" in content
        assert "review" in content

    def test_readme_mentions_store(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "store.py" in content

    def test_readme_mentions_feedback(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "feedback.py" in content

    def test_readme_mentions_web_app(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "app.py" in content

    def test_readme_mentions_render(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "render" in content

    def test_readme_mentions_sqlite(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "sqlite" in content

    def test_readme_mentions_synonym(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "synonym" in content

    def test_readme_mentions_combination_rules(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "combination" in content

    def test_readme_mentions_security(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").lower()
        assert "security" in content
        assert "sanitization" in content

    def test_readme_test_count_updated(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "248" in content

    def test_product_notes_mentions_feedback_loop(self):
        content = (PROJECT_ROOT / "notes" / "product_notes.md").read_text(encoding="utf-8").lower()
        assert "feedback" in content
        assert "synonym" in content

    def test_product_notes_mentions_flask(self):
        content = (PROJECT_ROOT / "notes" / "product_notes.md").read_text(encoding="utf-8").lower()
        assert "flask" in content

    def test_product_notes_mentions_sqlite(self):
        content = (PROJECT_ROOT / "notes" / "product_notes.md").read_text(encoding="utf-8").lower()
        assert "sqlite" in content
