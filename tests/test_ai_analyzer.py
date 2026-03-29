import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from symsafe.ai_analyzer import analyze_session, generate_bulk_synonyms
from symsafe.store import init_db, save_analysis, get_analysis


class TestAnalyzeSession:
    def test_returns_dict_on_success(self):
        mock_client = MagicMock()
        analysis_json = json.dumps({
            "clinical_summary": "Patient presented with mild headache.",
            "risk_assessment": {"ai_risk_was_appropriate": True, "explanation": "ok", "suggested_risk": "LOW", "reasoning": ""},
            "response_quality": [],
            "differential_considerations": [],
            "synonym_suggestions": [],
            "response_templates": [],
            "intake_observations": "",
            "review_priority": "routine",
            "priority_reason": "",
            "pattern_notes": "",
        })
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=analysis_json)]
        mock_client.messages.create.return_value = mock_response

        result = analyze_session(
            mock_client,
            {"intake_answers": {"concern": "headache"}},
            [{"user_input": "I have a headache", "assistant_response": "Let me help."}],
            {"high": ["chest pain"], "moderate": ["fever"]},
        )
        assert isinstance(result, dict)
        assert "clinical_summary" in result
        assert result["clinical_summary"] == "Patient presented with mild headache."

    def test_returns_fallback_on_api_failure(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")

        result = analyze_session(
            mock_client,
            {"intake_answers": {}},
            [],
            {"high": [], "moderate": []},
        )
        assert isinstance(result, dict)
        assert "unavailable" in result["clinical_summary"].lower()

    def test_handles_malformed_json(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON at all")]
        mock_client.messages.create.return_value = mock_response

        result = analyze_session(
            mock_client,
            {"intake_answers": {}},
            [],
            {"high": [], "moderate": []},
        )
        assert isinstance(result, dict)
        assert "unavailable" in result["clinical_summary"].lower()

    def test_returns_fallback_when_client_is_none(self):
        result = analyze_session(
            None,
            {"intake_answers": {}},
            [],
            {"high": [], "moderate": []},
        )
        assert isinstance(result, dict)
        assert "unavailable" in result["clinical_summary"].lower()


class TestBulkSynonyms:
    def test_returns_list(self):
        mock_client = MagicMock()
        suggestions = [
            {"phrase": "terrible headache", "confidence": 0.9},
            {"phrase": "splitting headache", "confidence": 0.85},
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(suggestions))]
        mock_client.messages.create.return_value = mock_response

        result = generate_bulk_synonyms(mock_client, "bad headache", "headache", "MODERATE")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["phrase"] == "terrible headache"

    def test_returns_empty_on_failure(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")

        result = generate_bulk_synonyms(mock_client, "test", "test", "HIGH")
        assert result == []


class TestAnalysisCache:
    def test_save_and_get_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path=db_path)

            analysis = {"clinical_summary": "Test analysis", "review_priority": "routine"}
            save_analysis("test_session", analysis, db_path=db_path)

            result = get_analysis("test_session", db_path=db_path)
            assert result is not None
            assert result["clinical_summary"] == "Test analysis"
            assert result["review_priority"] == "routine"

    def test_get_returns_none_for_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path=db_path)

            result = get_analysis("nonexistent_session", db_path=db_path)
            assert result is None
