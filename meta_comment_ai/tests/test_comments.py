from __future__ import annotations

import unittest
from unittest.mock import patch

from meta_comment_ai.services.comments import normalize_event
from meta_comment_ai.services.extraction import detect_language
from meta_comment_ai.api.inbox import _boolean_search
from meta_comment_ai.api.webhook import _event_job_id, iter_comment_events


class TestComments(unittest.TestCase):
    def test_normalize_instagram_comment_event(self):
        event = {
            "object": "instagram",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "comments",
                            "value": {
                                "comment_id": "1789",
                                "text": "price please",
                                "media_id": "1790",
                                "from": {"id": "u1", "username": "patient_user"},
                            },
                        }
                    ]
                }
            ],
        }
        result = normalize_event(event)
        assert result["platform"] == "Instagram"
        assert result["platform_comment_id"] == "1789"
        assert result["comment_text"] == "price please"
        assert result["commenter_username"] == "patient_user"

    def test_boolean_search_is_prefix_bounded(self):
        assert _boolean_search("kidney treatment") == "+kidney* +treatment*"

    def test_webhook_job_id_is_stable_and_bounded(self):
        payload = {"object": "instagram", "entry": [{"id": "123"}]}
        assert _event_job_id(payload) == _event_job_id(payload)
        assert len(_event_job_id(payload)) < 64

    @patch("meta_comment_ai.api.webhook._account_for_entry", return_value="MSA-00001")
    def test_batched_webhook_keeps_every_change(self, _account_lookup):
        payload = {
            "object": "instagram",
            "entry": [{"id": "ig-1", "changes": [{"value": {"id": "c1"}}, {"value": {"id": "c2"}}]}],
        }
        events = list(iter_comment_events(payload))
        assert len(events) == 2
        assert [normalize_event(event[0])["platform_comment_id"] for event in events] == ["c1", "c2"]
        assert all(event[2] == "MSA-00001" for event in events)

    def test_romanized_hindi_is_hinglish(self):
        assert detect_language("Mam mera treatment kasa hoga ji") == "hinglish"
