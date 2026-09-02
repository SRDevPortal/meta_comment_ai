from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from meta_comment_ai.api.sync import _sync_account_comments, _sync_source_names
from meta_comment_ai.meta_comment_ai.doctype.meta_social_account.meta_social_account import MetaSocialAccount
from meta_comment_ai.services.leads import _ensure_lead_source
from meta_comment_ai.tasks import SYNC_BATCH_SIZE, _mark_sync_error, sync_account_batch


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


class TestBatchedSync(unittest.TestCase):
    @patch("meta_comment_ai.tasks.frappe")
    def test_busy_account_exits_without_starting_duplicate_batch(self, frappe_mock):
        lock = MagicMock()
        lock.acquire.return_value = False
        frappe_mock.cache.lock.return_value = lock

        result = sync_account_batch("MSA-TEST", offset=25, total=100)

        self.assertEqual(result["skipped"], "sync already running")
        frappe_mock.get_all.assert_not_called()

    @patch("meta_comment_ai.tasks.now_datetime", return_value="2026-08-18 16:00:00")
    @patch("meta_comment_ai.api.sync._sync_source_names", return_value={"imported": 4, "sources": 25})
    @patch("meta_comment_ai.tasks.enqueue_account_batch")
    @patch("meta_comment_ai.tasks.frappe")
    def test_batch_queues_next_window(self, frappe_mock, enqueue_mock, sync_mock, _now):
        frappe_mock.get_doc.return_value = SimpleNamespace(name="MSA-TEST")
        frappe_mock.get_all.return_value = [f"MCS-{index}" for index in range(SYNC_BATCH_SIZE)]
        frappe_mock.db = MagicMock()

        result = sync_account_batch("MSA-TEST", offset=0, total=60)

        sync_mock.assert_called_once()
        enqueue_mock.assert_called_once_with("MSA-TEST", offset=SYNC_BATCH_SIZE, total=60)
        self.assertEqual(result["offset"], SYNC_BATCH_SIZE)

    @patch("meta_comment_ai.tasks.now_datetime", return_value="2026-08-18 16:00:00")
    @patch("meta_comment_ai.api.sync._sync_source_names", return_value={"imported": 1, "sources": 10})
    @patch("meta_comment_ai.tasks._refresh_connected_status")
    @patch("meta_comment_ai.tasks.enqueue_account_batch")
    @patch("meta_comment_ai.tasks.frappe")
    def test_last_batch_marks_account_active(self, frappe_mock, enqueue_mock, _refresh, _sync_mock, _now):
        frappe_mock.get_doc.return_value = SimpleNamespace(name="MSA-TEST")
        frappe_mock.get_all.return_value = [f"MCS-{index}" for index in range(10)]
        frappe_mock.db = MagicMock()

        sync_account_batch("MSA-TEST", offset=50, total=60)

        enqueue_mock.assert_not_called()
        final_update = frappe_mock.db.set_value.call_args.args[2]
        self.assertEqual(final_update["connector_status"], "Active")
        self.assertEqual(final_update["last_sync_at"], "2026-08-18 16:00:00")

    @patch("meta_comment_ai.tasks._refresh_connected_status")
    @patch("meta_comment_ai.tasks.frappe")
    def test_error_status_is_written_in_fresh_transaction(self, frappe_mock, _refresh):
        frappe_mock.db = MagicMock()

        _mark_sync_error("MSA-TEST", RuntimeError("batch failed"))

        frappe_mock.db.rollback.assert_called_once_with()
        frappe_mock.db.commit.assert_called_once_with()
        update = frappe_mock.db.set_value.call_args.args[2]
        self.assertEqual(update["connector_status"], "Error")
        self.assertEqual(update["last_error"], "batch failed")


class TestPartialSourceFailure(unittest.TestCase):
    @patch("meta_comment_ai.api.sync.time.sleep")
    @patch("meta_comment_ai.api.sync.upsert_comment_from_event", return_value="MCOM-1")
    @patch("meta_comment_ai.api.sync.graph.list_all_replies", return_value={"data": []})
    @patch("meta_comment_ai.api.sync.graph.list_all_comments")
    @patch("meta_comment_ai.api.sync.frappe")
    def test_inaccessible_source_does_not_abort_remaining_sources(
        self, frappe_mock, list_comments, _replies, _upsert, _sleep
    ):
        source_one = SimpleNamespace(name="MCS-1", source_id="deleted-post")
        source_two = SimpleNamespace(name="MCS-2", source_id="working-post")
        frappe_mock.get_doc.side_effect = [source_one, source_two]
        frappe_mock.db = MagicMock()
        list_comments.side_effect = [
            RuntimeError("Unsupported get request"),
            {"data": [{"id": "c1", "message": "hello", "from": {"id": "u1"}}]},
        ]

        result = _sync_source_names(SimpleNamespace(platform="Facebook", name="MSA-TEST"), ["MCS-1", "MCS-2"])

        self.assertEqual(result["sources"], 2)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["errors"][0]["source"], "MCS-1")
        self.assertEqual(list_comments.call_count, 2)


class TestLeadSourceCompatibility(unittest.TestCase):
    @patch("meta_comment_ai.services.leads.frappe")
    def test_uses_link_target_configured_on_crm_lead(self, frappe_mock):
        source_field = SimpleNamespace(options="Source")
        source_meta = SimpleNamespace(
            title_field=None,
            has_field=lambda fieldname: fieldname == "source_name",
        )
        frappe_mock.get_meta.side_effect = lambda doctype: (
            SimpleNamespace(get_field=lambda _fieldname: source_field)
            if doctype == "CRM Lead"
            else source_meta
        )
        frappe_mock.db.exists.side_effect = [True, False, True]

        result = _ensure_lead_source("Instagram")

        self.assertEqual(result, "Instagram Comment")
        values = frappe_mock.get_doc.call_args.args[0]
        self.assertEqual(values["doctype"], "Source")
        self.assertEqual(values["source_name"], "Instagram Comment")
