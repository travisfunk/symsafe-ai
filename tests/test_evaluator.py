import pytest
from unittest.mock import MagicMock
from symsafe.evaluator import run_auto_evaluation


class TestEvaluator:
    def test_uses_claude_haiku(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="- [x] Safe\n- [x] Empathetic")]
        mock_client.messages.create.return_value = mock_response
        run_auto_evaluation(mock_client, "I have chest pain", "Please seek care.", False)
        call_args = mock_client.messages.create.call_args
        model = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model == "claude-haiku-4-5-20251001", f"Evaluator should use claude-haiku-4-5-20251001, got: {model}"

    def test_returns_string_on_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Evaluation: Safe and empathetic.")]
        mock_client.messages.create.return_value = mock_response
        result = run_auto_evaluation(mock_client, "test", "response", False)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_error_string_on_failure(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        result = run_auto_evaluation(mock_client, "test", "response", False)
        assert "failed" in result.lower() or "error" in result.lower()

    def test_learning_mode_adds_educational_note(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Evaluation result")]
        mock_client.messages.create.return_value = mock_response
        run_auto_evaluation(mock_client, "test", "response", True)
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_content = messages[0]["content"]
        assert "educational" in user_content.lower() or "developer" in user_content.lower()
