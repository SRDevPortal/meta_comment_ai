from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime


def bootstrap_social_account(account: str):
    """Import connected accounts, discover content, and sync comments for one saved connector."""
    if not frappe.db.exists("Meta Social Account", account):
        return

    doc = frappe.get_doc("Meta Social Account", account)
    if not doc.is_active:
        return

    try:
        frappe.db.set_value(
            "Meta Social Account", account, {"connector_status": "Syncing", "last_error": ""}, update_modified=True
        )
        frappe.db.commit()
        if _is_master_token(doc):
            token = doc.get_password("access_token")
            if not token:
                return
            from meta_comment_ai.api.oauth import import_accounts

            result = import_accounts(token, doc)
            frappe.db.set_value(
                "Meta Social Account",
                doc.name,
                {"connector_status": "Active", "last_error": ""},
                update_modified=True,
            )
            for imported_account in result.get("accounts") or []:
                if imported_account != doc.name:
                    enqueue_account_sync(imported_account)
            return result

        return sync_one_account(account)
    except Exception:
        frappe.db.set_value(
            "Meta Social Account",
            account,
            {"connector_status": "Error", "last_error": frappe.get_traceback()[-1000:]},
            update_modified=True,
        )
        frappe.log_error(frappe.get_traceback(), "Meta Comment AI Bootstrap Failed")
        raise


def sync_one_account(account: str):
    from meta_comment_ai.api.sync import _sync_account_comments

    return _sync_account_comments(account)


def enqueue_account_bootstrap(account: str, force: bool = False):
    frappe.enqueue(
        "meta_comment_ai.tasks.bootstrap_social_account",
        queue="short",
        account=account,
        now=False,
        enqueue_after_commit=True,
        job_id=f"meta_comment_bootstrap_{account}_{frappe.generate_hash(length=8)}" if force else f"meta_comment_bootstrap_{account}",
        deduplicate=not force,
    )


def enqueue_account_sync(account: str):
    frappe.enqueue(
        "meta_comment_ai.tasks.sync_one_account",
        queue="short",
        account=account,
        now=False,
        enqueue_after_commit=True,
        job_id=f"meta_comment_sync_{account}",
        deduplicate=True,
    )


def sync_recent_comments():
    """Best-effort scheduled reconciliation for active accounts."""
    if not frappe.db.exists("DocType", "Meta Social Account"):
        return

    accounts = frappe.get_all(
        "Meta Social Account",
        filters={"is_active": 1, "parent_social_account": ["is", "not set"]},
        pluck="name",
    )
    for account in accounts:
        try:
            enqueue_account_bootstrap(account)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Meta Comment AI Sync Enqueue Failed")


def recover_stale_syncs():
    """Requeue a bounded batch of sync jobs that disappeared from Redis."""
    cutoff = add_to_date(now_datetime(), minutes=-15)
    accounts = frappe.get_all(
        "Meta Social Account",
        filters={
            "is_active": 1,
            "connector_status": ["in", ["Sync Queued", "Syncing"]],
            "modified": ["<=", cutoff],
        },
        fields=["name"],
        order_by="modified asc",
        limit_start=0,
        limit_page_length=100,
    )
    for row in accounts:
        enqueue_account_bootstrap(row.name, force=True)


def _is_master_token(doc) -> bool:
    return (
        doc.auth_method == "Access Token"
        and doc.access_token_mode == "User Long-Lived Token"
        and not doc.page_id
        and not doc.instagram_business_account_id
    )
