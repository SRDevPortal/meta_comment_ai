from __future__ import annotations

import unittest

from meta_comment_ai.services.comments import normalize_event


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
