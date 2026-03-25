import pytest
from pathlib import Path
from symsafe.config import BASE_DIR, load_base_prompt

class TestConfig:
    def test_base_dir_exists(self):
        assert BASE_DIR.exists()

    def test_base_dir_has_prompts(self):
        assert (BASE_DIR / "prompts").exists()

    def test_base_dir_has_requirements(self):
        assert (BASE_DIR / "requirements.txt").exists()

    def test_load_base_prompt_returns_string(self):
        prompt = load_base_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100
