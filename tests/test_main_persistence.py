from pathlib import Path

import pytest


MAIN_PATH = Path(__file__).resolve().parent.parent / "symsafe" / "main.py"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "symsafe" / "config.py"
GITIGNORE_PATH = Path(__file__).resolve().parent.parent / ".gitignore"


def _read(path):
    return path.read_text(encoding="utf-8")


class TestMainPersistence:
    def test_main_imports_store(self):
        content = _read(MAIN_PATH)
        assert "store" in content

    def test_main_imports_feedback(self):
        content = _read(MAIN_PATH)
        assert "feedback" in content

    def test_main_calls_init_db(self):
        content = _read(MAIN_PATH)
        assert "init_db" in content

    def test_main_calls_save_session(self):
        content = _read(MAIN_PATH)
        assert "save_session" in content

    def test_main_calls_save_exchange(self):
        content = _read(MAIN_PATH)
        assert "save_exchange" in content

    def test_main_calls_detect_gap(self):
        content = _read(MAIN_PATH)
        assert "detect_classifier_gap" in content or "detect_gap" in content

    def test_gitignore_has_data(self):
        content = _read(GITIGNORE_PATH)
        assert "data/" in content

    def test_config_has_db_path(self):
        content = _read(CONFIG_PATH)
        assert "DB_PATH" in content
