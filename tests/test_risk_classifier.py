import pytest
from symsafe.risk_classifier import classify_risk

class TestRiskClassification:
    def test_chest_pain_is_high_risk(self):
        level, flags = classify_risk("I have chest pain")
        assert "HIGH" in level.upper()
        assert "chest pain" in flags

    def test_headache_is_not_high_risk(self):
        level, flags = classify_risk("I have a headache")
        assert "HIGH" not in level.upper()

    def test_shortness_of_breath_is_high_risk(self):
        level, flags = classify_risk("I'm having shortness of breath")
        assert "HIGH" in level.upper()

    def test_empty_input_is_low_risk(self):
        level, flags = classify_risk("")
        assert "LOW" in level.upper()
        assert len(flags) == 0

    def test_suicidal_is_high_risk(self):
        level, flags = classify_risk("I feel suicidal")
        assert "HIGH" in level.upper()

    def test_cant_breathe_is_high_risk(self):
        level, flags = classify_risk("I can't breathe")
        assert "HIGH" in level.upper()

    def test_stroke_is_high_risk(self):
        level, flags = classify_risk("I think I'm having a stroke")
        assert "HIGH" in level.upper()

    def test_fever_is_moderate_risk(self):
        level, flags = classify_risk("I have a fever")
        assert "MODERATE" in level.upper()
        assert "fever" in flags

    def test_fracture_is_moderate_risk(self):
        level, flags = classify_risk("I think I have a fracture")
        assert "MODERATE" in level.upper()

    def test_normal_greeting_is_low_risk(self):
        level, flags = classify_risk("Hello, how are you?")
        assert "LOW" in level.upper()
        assert len(flags) == 0

    def test_case_insensitive(self):
        level, flags = classify_risk("I have CHEST PAIN and SHORTNESS OF BREATH")
        assert "HIGH" in level.upper()

    def test_returns_tuple(self):
        result = classify_risk("hello")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_multiple_high_flags_collected(self):
        level, flags = classify_risk("I have chest pain and shortness of breath")
        assert "HIGH" in level.upper()
        assert len(flags) >= 2

    def test_high_overrides_moderate(self):
        level, flags = classify_risk("I have chest pain and a fever")
        assert "HIGH" in level.upper()

    def test_combination_headache_vision_is_high(self):
        level, flags = classify_risk("I have a headache with vision changes")
        assert "HIGH" in level.upper()

    def test_combination_partial_not_triggered(self):
        level, flags = classify_risk("I have a headache")
        assert "HIGH" not in level.upper()
