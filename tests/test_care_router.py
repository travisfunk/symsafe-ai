import pytest
from symsafe.care_router import get_care_guidance, merge_care_level


class TestGetCareGuidance:
    def test_emergency_has_all_fields(self):
        result = get_care_guidance("emergency")
        assert isinstance(result, dict)
        assert "where" in result
        assert "why" in result
        assert "right_now" in result

    def test_emergency_mentions_911(self):
        result = get_care_guidance("emergency")
        assert "911" in result["where"]

    def test_urgent_care_mentions_clinic(self):
        result = get_care_guidance("urgent_care")
        assert "urgent care" in result["where"].lower() or "clinic" in result["where"].lower()

    def test_primary_care_mentions_doctor(self):
        result = get_care_guidance("primary_care")
        assert "doctor" in result["where"].lower() or "primary care" in result["where"].lower()

    def test_telehealth_mentions_virtual(self):
        result = get_care_guidance("telehealth")
        assert "virtual" in result["where"].lower() or "telehealth" in result["where"].lower()

    def test_self_care_mentions_home(self):
        result = get_care_guidance("self_care")
        assert "home" in result["where"].lower() or "monitor" in result["where"].lower()

    def test_all_levels_return_dict(self):
        for level in ["emergency", "urgent_care", "primary_care", "telehealth", "self_care"]:
            result = get_care_guidance(level)
            assert isinstance(result, dict)
            assert len(result["where"]) > 10
            assert len(result["why"]) > 10
            assert len(result["right_now"]) > 10

    def test_unknown_level_defaults_to_self_care(self):
        result = get_care_guidance("unknown_value")
        assert "home" in result["where"].lower() or "monitor" in result["where"].lower()


class TestMergeCareLevel:
    def test_high_risk_upgrades_primary_care(self):
        result = merge_care_level("🔴 HIGH RISK", "primary_care")
        assert result in ["emergency", "urgent_care"]

    def test_high_risk_upgrades_self_care(self):
        result = merge_care_level("🔴 HIGH RISK", "self_care")
        assert result in ["emergency", "urgent_care"]

    def test_high_risk_keeps_emergency(self):
        result = merge_care_level("🔴 HIGH RISK", "emergency")
        assert result == "emergency"

    def test_moderate_risk_upgrades_self_care(self):
        result = merge_care_level("🟡 MODERATE RISK", "self_care")
        assert result in ["primary_care", "telehealth", "urgent_care"]

    def test_moderate_risk_keeps_urgent_care(self):
        result = merge_care_level("🟡 MODERATE RISK", "urgent_care")
        assert result == "urgent_care"

    def test_low_risk_trusts_gpt(self):
        result = merge_care_level("🟢 LOW RISK", "telehealth")
        assert result == "telehealth"

    def test_low_risk_keeps_self_care(self):
        result = merge_care_level("🟢 LOW RISK", "self_care")
        assert result == "self_care"

    def test_emergency_never_downgraded(self):
        result = merge_care_level("🟢 LOW RISK", "emergency")
        assert result == "emergency"

    def test_unknown_gpt_level_defaults(self):
        result = merge_care_level("🟢 LOW RISK", "garbage")
        assert result == "self_care"
