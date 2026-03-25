import pytest
from symsafe.symptom_tree import match_symptom_tree, load_symptom_tree

class TestSymptomTreeMatch:
    def test_match_single_symptom(self):
        tree = {"chest pain": "Seek emergency care.", "headache": "Monitor symptoms."}
        result = match_symptom_tree("I have chest pain", tree)
        assert len(result) == 1
        assert result[0][0] == "chest pain"

    def test_match_multiple_symptoms(self):
        tree = {"chest pain": "Seek emergency care.", "headache": "Monitor symptoms."}
        result = match_symptom_tree("I have chest pain and a headache", tree)
        assert len(result) == 2

    def test_match_case_insensitive(self):
        tree = {"chest pain": "Seek emergency care."}
        result = match_symptom_tree("I have CHEST PAIN", tree)
        assert len(result) == 1

    def test_no_match(self):
        tree = {"chest pain": "Seek emergency care."}
        result = match_symptom_tree("I feel fine today", tree)
        assert len(result) == 0

    def test_empty_input(self):
        tree = {"chest pain": "Seek emergency care."}
        result = match_symptom_tree("", tree)
        assert len(result) == 0

    def test_empty_tree(self):
        result = match_symptom_tree("I have chest pain", {})
        assert len(result) == 0

    def test_returns_list_of_tuples(self):
        tree = {"fever": "Monitor temperature."}
        result = match_symptom_tree("I have a fever", tree)
        assert isinstance(result, list)
        assert isinstance(result[0], tuple)

class TestSymptomTreeLoad:
    def test_load_returns_dict(self):
        tree = load_symptom_tree()
        assert isinstance(tree, dict)

    def test_load_has_entries(self):
        tree = load_symptom_tree()
        assert len(tree) > 0

    def test_load_contains_chest_pain(self):
        tree = load_symptom_tree()
        assert "chest pain" in tree
