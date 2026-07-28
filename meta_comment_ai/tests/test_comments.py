from __future__ import annotations

import unittest

from meta_comment_ai.services.comments import normalize_event
from meta_comment_ai.api.inbox import _boolean_search
from meta_comment_ai.api.webhook import _event_job_id


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
