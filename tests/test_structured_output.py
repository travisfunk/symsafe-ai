import pytest
import json
from unittest.mock import MagicMock
from symsafe.agent import get_assistant_response


class TestStructuredOutput:
    def _mock_client(self, content):
        mock = MagicMock()
        mock.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=content))
        ]
        return mock

    def test_returns_dict_on_valid_json(self):
        response_json = json.dumps({
            "response": "I understand your concern.",
            "risk_level": "LOW",
            "risk_flags": [],
            "follow_up_questions": []
        })
        client = self._mock_client(response_json)
        result = get_assistant_response(client, [{"role": "user", "content": "hello"}])
        assert isinstance(result, dict)
        assert "response" in result
        assert "risk_level" in result
        assert "risk_flags" in result
        assert "follow_up_questions" in result

    def test_returns_dict_with_code_fences(self):
        response_json = '```json\n' + json.dumps({
            "response": "Please seek care.",
            "risk_level": "HIGH",
            "risk_flags": ["chest pain"],
            "follow_up_questions": ["When did it start?"]
        }) + '\n```'
        client = self._mock_client(response_json)
        result = get_assistant_response(client, [{"role": "user", "content": "chest pain"}])
        assert isinstance(result, dict)
        assert result["risk_level"] == "HIGH"

    def test_fallback_on_invalid_json(self):
        client = self._mock_client("I'm sorry to hear that. Please see a doctor.")
        result = get_assistant_response(client, [{"role": "user", "content": "I feel sick"}])
        assert isinstance(result, dict)
        assert result["response"] == "I'm sorry to hear that. Please see a doctor."
        assert result["risk_level"] == "LOW"
        assert result["risk_flags"] == []
        assert result["follow_up_questions"] == []

    def test_returns_none_on_api_failure(self):
        mock = MagicMock()
        mock.chat.completions.create.side_effect = Exception("API Error")
        result = get_assistant_response(mock, [{"role": "user", "content": "test"}])
        assert result is None

    def test_follow_up_questions_preserved(self):
        response_json = json.dumps({
            "response": "Tell me more.",
            "risk_level": "MODERATE",
            "risk_flags": ["fever"],
            "follow_up_questions": ["How long have you had the fever?", "What is your temperature?"]
        })
        client = self._mock_client(response_json)
        result = get_assistant_response(client, [{"role": "user", "content": "I have a fever"}])
        assert len(result["follow_up_questions"]) == 2

    def test_still_uses_gpt4o(self):
        response_json = json.dumps({
            "response": "Hi there.", "risk_level": "LOW",
            "risk_flags": [], "follow_up_questions": []
        })
        client = self._mock_client(response_json)
        get_assistant_response(client, [{"role": "user", "content": "hello"}])
        call_args = client.chat.completions.create.call_args
        model = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model == "gpt-4o", f"Agent should use gpt-4o, got: {model}"

    def test_care_level_in_response(self):
        response_json = json.dumps({
            "response": "Please seek care.",
            "risk_level": "HIGH",
            "risk_flags": ["chest pain"],
            "follow_up_questions": [],
            "care_level": "emergency"
        })
        client = self._mock_client(response_json)
        result = get_assistant_response(client, [{"role": "user", "content": "chest pain"}])
        assert result["care_level"] == "emergency"

    def test_fallback_care_level_is_self_care(self):
        client = self._mock_client("Just plain text, no JSON here.")
        result = get_assistant_response(client, [{"role": "user", "content": "hello"}])
        assert result["care_level"] == "self_care"
