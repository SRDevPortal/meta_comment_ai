from __future__ import annotations

import unittest

from meta_comment_ai.services.ai import validate_ai_result
from meta_comment_ai.services.extraction import detect_language, extract_phone_numbers
from meta_comment_ai.services.policy import classify_risk


class TestExtractionPolicyAI(unittest.TestCase):
    def test_extracts_indian_phone_numbers(self):
        assert extract_phone_numbers("Call +91 98765 43210 or 09876543210") == ["9876543210"]

    def test_detects_hindi_and_hinglish(self):
        assert detect_language("मुझे दर्द है") == "hi"
        assert detect_language("mujhe ilaj chahiye") == "hinglish"

    def test_classifies_medical_and_urgent(self):
        assert classify_risk("which medicine dose for pain") == "Medical"
        assert classify_risk("severe pain and breathing issue") == "Urgent"

    def test_ai_result_forces_medical_escalation(self):
        result = validate_ai_result(
            {"action": "draft_public_reply", "reply_text": "Take this medicine", "confidence": 0.9},
            fallback_text="medicine for pain?",
            fallback_language="en",
            fallback_risk="Medical",
            phones=[],
        )
        assert result["action"] == "escalate"
        assert result["risk_level"] == "Medical"

    def test_unknown_ai_action_falls_back(self):
        result = validate_ai_result(
            {"action": "prescribe", "reply_text": ""},
            fallback_text="price?",
            fallback_language="en",
            fallback_risk="Low",
            phones=[],
        )
        assert result["action"] == "draft_public_reply"
        assert result["reply_text"]
