from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from meta_comment_ai import document_privacy, hooks, number_privacy


class TestMetaCommentNumberPrivacy(unittest.TestCase):
    def test_restricted_projection_masks_phone_fields_and_comment_text(self):
        raw = {
            "comment": {
                "phone_numbers": "9876543210\n9123456789",
                "comment_text": "Please call +91 98765 43210",
                "commenter_name": "Customer 9876543210",
                "raw_event_json": '{"message":"9876543210"}',
            },
            "actions": [
                {
                    "error": "Delivery to 9876543210 failed",
                    "request_json": '{"phone":"9876543210"}',
                    "response_json": '{"phone":"9876543210"}',
                }
            ],
        }
        with patch("meta_comment_ai.number_privacy.restricted", return_value=True):
            result = number_privacy.project_response(raw)

        self.assertNotIn("9876543210", str(result))
        self.assertEqual(
            result["comment"]["phone_numbers"],
            "******3210\n******6789",
        )
        self.assertNotIn("raw_event_json", result["comment"])
        self.assertNotIn("request_json", result["actions"][0])
        self.assertNotIn("response_json", result["actions"][0])
        self.assertEqual(raw["comment"]["phone_numbers"], "9876543210\n9123456789")

    def test_full_visibility_preserves_response_object(self):
        raw = {"phone_numbers": "9876543210", "raw_event_json": "{}"}
        with patch("meta_comment_ai.number_privacy.restricted", return_value=False):
            self.assertIs(number_privacy.project_response(raw), raw)

    def test_already_masked_phone_is_stable(self):
        raw = {"phone_numbers": "******3210"}
        with patch("meta_comment_ai.number_privacy.restricted", return_value=True):
            self.assertEqual(
                number_privacy.project_response(raw)["phone_numbers"],
                "******3210",
            )

    def test_phone_search_requires_full_visibility(self):
        with patch("meta_comment_ai.number_privacy.restricted", return_value=True):
            with self.assertRaises(frappe.PermissionError):
                number_privacy.guard_phone_search("9876543210")
            number_privacy.guard_phone_search("help with appointment")

        with patch("meta_comment_ai.number_privacy.restricted", return_value=False):
            number_privacy.guard_phone_search("9876543210")

    def test_raw_document_request_detection_covers_rest_print_and_generic_api(self):
        self.assertTrue(
            document_privacy.is_raw_request(
                "/api/resource/Meta%20Comment/COMMENT-1",
                {},
            )
        )
        self.assertTrue(
            document_privacy.is_raw_request(
                "/printview",
                {"doctype": "Meta Comment Action", "name": "ACTION-1"},
            )
        )
        self.assertTrue(
            document_privacy.is_raw_request(
                "/api/method/frappe.client.get",
                {"doctype": "Meta Comment"},
            )
        )
        self.assertFalse(
            document_privacy.is_raw_request(
                "/api/resource/Meta%20Content%20Source/SOURCE-1",
                {},
            )
        )

    def test_raw_document_guard_blocks_restricted_http_access(self):
        request = SimpleNamespace(path="/api/resource/Meta%20Comment/COMMENT-1")
        with (
            patch.object(document_privacy.frappe.local, "request", request, create=True),
            patch.object(
                document_privacy.frappe.local,
                "form_dict",
                frappe._dict(),
                create=True,
            ),
            patch("meta_comment_ai.document_privacy.restricted", return_value=True),
        ):
            with self.assertRaises(frappe.PermissionError):
                document_privacy.guard_request()

    def test_inbox_endpoints_use_browser_projection(self):
        from meta_comment_ai.api import inbox

        for endpoint in (
            inbox.get_accounts,
            inbox.get_connected_accounts,
            inbox.get_sources,
            inbox.get_source_detail,
            inbox.get_comments,
            inbox.get_comment_detail,
        ):
            with self.subTest(endpoint=endpoint.__name__):
                self.assertTrue(hasattr(endpoint, "__wrapped__"))

    def test_review_mutations_are_post_only(self):
        from meta_comment_ai.api import review

        for endpoint in (
            review.create_comment_action,
            review.generate_ai_action,
            review.approve_action,
            review.execute_action_now,
            review.reject_action,
            review.retry_action,
        ):
            with self.subTest(endpoint=endpoint.__name__):
                self.assertEqual(
                    frappe.allowed_http_methods_for_whitelisted_func[endpoint],
                    ["POST"],
                )

    def test_auth_hook_registers_raw_document_guard(self):
        self.assertIn(
            "meta_comment_ai.document_privacy.guard_request",
            hooks.auth_hooks,
        )

    def test_ai_internal_phone_values_remain_raw(self):
        from meta_comment_ai.services.ai import _local_recommendation

        result = _local_recommendation(
            "capture_lead_and_hide",
            "Call 9876543210",
            "en",
            "Low",
            ["9876543210"],
            "Phone captured",
        )
        self.assertEqual(result["lead_phone_numbers"], ["9876543210"])
