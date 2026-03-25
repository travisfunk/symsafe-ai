import pytest
import json
from unittest.mock import MagicMock
from symsafe.agent import get_assistant_response


class TestAgent:
    def test_returns_dict_on_success(self):
        mock_client = MagicMock()
        response_json = json.dumps({
            "response": "I understand your concern.",
            "risk_level": "LOW",
            "risk_flags": [],
            "follow_up_questions": []
        })
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=response_json))
        ]
        messages = [{"role": "user", "content": "I have a headache"}]
        result = get_assistant_response(mock_client, messages)
        assert isinstance(result, dict)
        assert result["response"] == "I understand your concern."

    def test_returns_none_on_failure(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        messages = [{"role": "user", "content": "test"}]
        result = get_assistant_response(mock_client, messages)
        assert result is None

    def test_calls_gpt4o(self):
        mock_client = MagicMock()
        response_json = json.dumps({
            "response": "response", "risk_level": "LOW",
            "risk_flags": [], "follow_up_questions": []
        })
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=response_json))
        ]
        messages = [{"role": "user", "content": "test"}]
        get_assistant_response(mock_client, messages)
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("model") == "gpt-4o" or call_args[1].get("model") == "gpt-4o"
