"""Tests for the patient-facing banner logic that decouples display from internal risk."""

import unittest
from pathlib import Path

from symsafe.web.app import determine_patient_banner


class TestPatientBanner(unittest.TestCase):
    """Test determine_patient_banner() returns proportionate patient-facing levels."""

    def test_both_high_is_emergency(self):
        banner, care = determine_patient_banner("HIGH", "HIGH", ["chest pain"], "emergency")
        assert banner == "emergency"

    def test_local_high_gpt_low_is_attention(self):
        banner, care = determine_patient_banner("HIGH", "LOW", ["chest tightness"], "urgent_care")
        assert banner == "attention"

    def test_local_high_gpt_moderate_is_attention(self):
        banner, care = determine_patient_banner("HIGH", "MODERATE", ["chest tightness"], "urgent_care")
        assert banner == "attention"

    def test_both_moderate_is_moderate(self):
        banner, care = determine_patient_banner("MODERATE", "MODERATE", ["fever"], "primary_care")
        assert banner == "moderate"

    def test_both_low_is_none(self):
        banner, care = determine_patient_banner("LOW", "LOW", [], "self_care")
        assert banner == "none"

    def test_combination_rule_forces_emergency(self):
        flags = ["headache", "combination:headache+vision"]
        banner, care = determine_patient_banner("HIGH", "LOW", flags, "urgent_care")
        assert banner == "emergency"

    def test_attention_downgrades_care_to_urgent(self):
        banner, care = determine_patient_banner("HIGH", "LOW", ["chest tightness"], "emergency")
        assert banner == "attention"
        assert care == "urgent_care"

    def test_emergency_keeps_emergency_care(self):
        banner, care = determine_patient_banner("HIGH", "HIGH", ["chest pain"], "emergency")
        assert banner == "emergency"
        assert care == "emergency"


class TestBannerInTemplate(unittest.TestCase):
    """Test that the index.html template contains the new banner text."""

    @classmethod
    def setUpClass(cls):
        template_path = Path(__file__).resolve().parent.parent / "symsafe" / "web" / "templates" / "index.html"
        cls.html = template_path.read_text(encoding="utf-8")

    def test_index_has_emergency_banner_text(self):
        assert "could be serious" in self.html

    def test_index_has_attention_banner_text(self):
        assert "no need to panic" in self.html

    def test_index_has_moderate_banner_text(self):
        assert "worth getting checked" in self.html


if __name__ == "__main__":
    unittest.main()
