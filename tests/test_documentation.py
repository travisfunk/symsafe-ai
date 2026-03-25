import pytest
from pathlib import Path

SYMSAFE_DIR = Path(__file__).resolve().parent.parent / "symsafe"

EMOJI_STRINGS = [
    "\u2705", "\U0001f534", "\U0001f7e2", "\U0001f7e1", "\U0001f4cb",
    "\U0001f916", "\U0001f4d8", "\u26a0\ufe0f", "\U0001f464", "\U0001f44b",
    "\U0001f4cd", "\U0001f4a1", "\U0001f4c4",
]


class TestModuleDocstrings:
    def test_config_has_docstring(self):
        content = (SYMSAFE_DIR / "config.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_agent_has_docstring(self):
        content = (SYMSAFE_DIR / "agent.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_evaluator_has_docstring(self):
        content = (SYMSAFE_DIR / "evaluator.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_risk_classifier_has_docstring(self):
        content = (SYMSAFE_DIR / "risk_classifier.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_symptom_tree_has_docstring(self):
        content = (SYMSAFE_DIR / "symptom_tree.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_care_router_has_docstring(self):
        content = (SYMSAFE_DIR / "care_router.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_intake_has_docstring(self):
        content = (SYMSAFE_DIR / "intake.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_report_has_docstring(self):
        content = (SYMSAFE_DIR / "report.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_logger_has_docstring(self):
        content = (SYMSAFE_DIR / "logger.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_main_has_docstring(self):
        content = (SYMSAFE_DIR / "main.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')

    def test_init_has_docstring(self):
        content = (SYMSAFE_DIR / "__init__.py").read_text(encoding="utf-8")
        assert content.lstrip().startswith('"""')


class TestNoEmojiComments:
    def test_no_emoji_in_comments(self):
        for py_file in SYMSAFE_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for line_num, line in enumerate(content.split("\n"), 1):
                stripped = line.lstrip()
                if not stripped.startswith("#"):
                    continue
                for emoji in EMOJI_STRINGS:
                    assert emoji not in stripped, (
                        f"Emoji {repr(emoji)} found in comment on line {line_num} "
                        f"of {py_file.name}: {stripped.strip()}"
                    )


class TestFunctionDocstrings:
    def test_classify_risk_has_docstring(self):
        from symsafe.risk_classifier import classify_risk
        assert classify_risk.__doc__ is not None and len(classify_risk.__doc__) > 20

    def test_get_assistant_response_has_docstring(self):
        from symsafe.agent import get_assistant_response
        assert get_assistant_response.__doc__ is not None and len(get_assistant_response.__doc__) > 20

    def test_run_auto_evaluation_has_docstring(self):
        from symsafe.evaluator import run_auto_evaluation
        assert run_auto_evaluation.__doc__ is not None and len(run_auto_evaluation.__doc__) > 20

    def test_get_care_guidance_has_docstring(self):
        from symsafe.care_router import get_care_guidance
        assert get_care_guidance.__doc__ is not None and len(get_care_guidance.__doc__) > 20

    def test_merge_care_level_has_docstring(self):
        from symsafe.care_router import merge_care_level
        assert merge_care_level.__doc__ is not None and len(merge_care_level.__doc__) > 20

    def test_match_symptom_tree_has_docstring(self):
        from symsafe.symptom_tree import match_symptom_tree
        assert match_symptom_tree.__doc__ is not None and len(match_symptom_tree.__doc__) > 20

    def test_run_intake_has_docstring(self):
        from symsafe.intake import run_intake
        assert run_intake.__doc__ is not None and len(run_intake.__doc__) > 20

    def test_format_intake_context_has_docstring(self):
        from symsafe.intake import format_intake_context
        assert format_intake_context.__doc__ is not None and len(format_intake_context.__doc__) > 20

    def test_generate_report_has_docstring(self):
        from symsafe.report import generate_report
        assert generate_report.__doc__ is not None and len(generate_report.__doc__) > 20

    def test_save_report_has_docstring(self):
        from symsafe.report import save_report
        assert save_report.__doc__ is not None and len(save_report.__doc__) > 20
