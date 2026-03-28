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
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_json)]
        mock_client.messages.create.return_value = mock_response
        messages = [{"role": "user", "content": "I have a headache"}]
        result = get_assistant_response(mock_client, messages)
        assert isinstance(result, dict)
        assert result["response"] == "I understand your concern."

    def test_returns_none_on_failure(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        messages = [{"role": "user", "content": "test"}]
        result = get_assistant_response(mock_client, messages)
        assert result is None

    def test_calls_claude(self):
        mock_client = MagicMock()
        response_json = json.dumps({
            "response": "response", "risk_level": "LOW",
            "risk_flags": [], "follow_up_questions": []
        })
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_json)]
        mock_client.messages.create.return_value = mock_response
        messages = [{"role": "user", "content": "test"}]
        get_assistant_response(mock_client, messages)
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs.get("model") == "claude-sonnet-4-20250514" or call_args[1].get("model") == "claude-sonnet-4-20250514"
