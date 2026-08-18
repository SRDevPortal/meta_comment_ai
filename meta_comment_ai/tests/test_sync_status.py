from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from meta_comment_ai.api.sync import _sync_account_comments
from meta_comment_ai.meta_comment_ai.doctype.meta_social_account.meta_social_account import MetaSocialAccount


class TestSyncStatus(unittest.TestCase):
    def setUp(self):
        self.account = SimpleNamespace(
            name="MSA-TEST",
            platform="Facebook",
            auth_method="Access Token",
            access_token_mode="Page Access Token",
            page_id="page-1",
            instagram_business_account_id=None,
            sync_source_ids="",
        )

    @patch("meta_comment_ai.api.sync.now_datetime", return_value="2026-08-18 12:00:00")
    @patch("meta_comment_ai.api.sync.ensure_manual_sources", return_value=[])
    @patch("meta_comment_ai.api.sync._discover_content_sources", return_value={"sources": []})
    @patch("meta_comment_ai.api.sync.frappe")
    def test_no_sources_finishes_as_active(self, frappe_mock, _discover, _manual, _now):
        frappe_mock.get_doc.return_value = self.account
        frappe_mock.db = MagicMock()

        result = _sync_account_comments(self.account.name)

        self.assertTrue(result["success"])
        self.assertEqual(result["sources"], 0)
        self.assertEqual(
            frappe_mock.db.set_value.call_args_list,
            [
                call(
                    "Meta Social Account",
                    self.account.name,
                    {"connector_status": "Syncing", "last_error": ""},
                    update_modified=True,
                ),
                call(
                    "Meta Social Account",
                    self.account.name,
                    {
                        "last_sync_at": "2026-08-18 12:00:00",
                        "last_error": "",
                        "connector_status": "Active",
                    },
                    update_modified=True,
                ),
            ],
        )

    @patch("meta_comment_ai.api.sync._discover_content_sources", side_effect=RuntimeError("Meta API failed"))
    @patch("meta_comment_ai.api.sync.frappe")
    def test_discovery_failure_finishes_as_error(self, frappe_mock, _discover):
        frappe_mock.get_doc.return_value = self.account
        frappe_mock.db = MagicMock()

        with self.assertRaisesRegex(RuntimeError, "Meta API failed"):
            _sync_account_comments(self.account.name)

        final_update = frappe_mock.db.set_value.call_args_list[-1].args[2]
        self.assertEqual(final_update["connector_status"], "Error")
        self.assertEqual(final_update["last_error"], "Meta API failed")


class TestAccountNameSanitization(unittest.TestCase):
    def test_access_token_is_removed_from_account_name(self):
        doc = SimpleNamespace(
            auth_method="Access Token",
            account_name="secret-token",
            account_label="Main Connection",
            get_password=lambda _fieldname: "secret-token",
        )

        MetaSocialAccount._remove_token_from_account_name(doc)

        self.assertEqual(doc.account_name, "Main Connection")
