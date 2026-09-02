from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime


SYNC_BATCH_SIZE = 25
SYNC_JOB_TIMEOUT = 1500
ACCOUNT_LOCK_TIMEOUT = SYNC_JOB_TIMEOUT + 60


def _acquire_account_lock(account: str):
    """Return a non-blocking Redis lock so duplicate recovery jobs exit harmlessly."""
    lock = frappe.cache.lock(f"meta_comment_sync_lock:{account}", timeout=ACCOUNT_LOCK_TIMEOUT)
    return lock if lock.acquire(blocking=False) else None


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
            lock = _acquire_account_lock(account)
            if not lock:
                return {"success": True, "account": account, "skipped": "sync already running"}
            try:
                token = doc.get_password("access_token")
                if not token:
                    return
                from meta_comment_ai.api.oauth import import_accounts

                result = import_accounts(token, doc)
                frappe.db.set_value(
                    "Meta Social Account",
                    doc.name,
                    {"connector_status": "Active", "last_error": "", "last_sync_at": now_datetime()},
                    update_modified=True,
                )
                for imported_account in result.get("accounts") or []:
                    if imported_account != doc.name:
                        enqueue_account_sync(imported_account)
                return result
            finally:
                lock.release()

        return sync_one_account(account)
    except Exception as exc:
        _mark_sync_error(account, exc)
        frappe.log_error(frappe.get_traceback(), "Meta Comment AI Bootstrap Failed")
        raise


def sync_one_account(account: str):
    """Discover sources once, then hand comment sync to bounded long-queue jobs."""
    lock = _acquire_account_lock(account)
    if not lock:
        return {"success": True, "account": account, "skipped": "sync already running"}
    try:
        return _sync_one_account(account)
    finally:
        lock.release()


def _sync_one_account(account: str):
    from meta_comment_ai.api.sync import _discover_content_sources, ensure_manual_sources

    doc = frappe.get_doc("Meta Social Account", account)
    frappe.db.set_value(
        "Meta Social Account", account, {"connector_status": "Syncing", "last_error": ""}, update_modified=True
    )
    frappe.db.commit()
    try:
        _discover_content_sources(account)
        ensure_manual_sources(doc)
        total = frappe.db.count("Meta Content Source", {"social_account": account})
        if not total:
            frappe.db.set_value(
                "Meta Social Account",
                account,
                {"connector_status": "Active", "last_error": "", "last_sync_at": now_datetime()},
                update_modified=True,
            )
            return {"success": True, "account": account, "sources": 0}
        enqueue_account_batch(account, offset=0, total=total)
        return {"success": True, "account": account, "queued_sources": total}
    except Exception as exc:
        _mark_sync_error(account, exc)
        raise


def sync_account_batch(account: str, offset: int, total: int):
    """Process one stable source window and enqueue its successor."""
    from meta_comment_ai.api.sync import _sync_source_names

    lock = _acquire_account_lock(account)
    if not lock:
        return {
            "success": True,
            "account": account,
            "offset": int(offset),
            "total": int(total),
            "skipped": "sync already running",
        }
    try:
        doc = frappe.get_doc("Meta Social Account", account)
        names = frappe.get_all(
            "Meta Content Source",
            filters={"social_account": account},
            pluck="name",
            order_by="name asc",
            limit_start=int(offset),
            limit_page_length=SYNC_BATCH_SIZE,
        )
        result = _sync_source_names(doc, names)
        next_offset = int(offset) + len(names)
        if names and next_offset < int(total):
            frappe.db.set_value("Meta Social Account", account, "modified", now_datetime(), update_modified=False)
            frappe.db.commit()
            enqueue_account_batch(account, offset=next_offset, total=total)
        else:
            failed_sources = frappe.db.count(
                "Meta Content Source", {"social_account": account, "last_error": ["is", "set"]}
            )
            warning = f"{failed_sources} inaccessible/deleted source(s) skipped; other content synced." if failed_sources else ""
            frappe.db.set_value(
                "Meta Social Account",
                account,
                {"connector_status": "Active", "last_error": warning, "last_sync_at": now_datetime()},
                update_modified=True,
            )
            _refresh_connected_status(account)
        return {**result, "account": account, "offset": next_offset, "total": total}
    except Exception as exc:
        _mark_sync_error(account, exc)
        raise
    finally:
        lock.release()


def enqueue_account_batch(account: str, offset: int, total: int):
    frappe.enqueue(
        "meta_comment_ai.tasks.sync_account_batch",
        queue="long",
        timeout=SYNC_JOB_TIMEOUT,
        account=account,
        offset=int(offset),
        total=int(total),
        now=False,
        enqueue_after_commit=True,
        job_id=f"meta_comment_batch_{account}_{int(offset)}",
        deduplicate=True,
    )


def _mark_sync_error(account: str, exc: Exception):
    # RQ rolls back the failed job transaction, so write the status in a fresh transaction.
    frappe.db.rollback()
    frappe.db.set_value(
        "Meta Social Account",
        account,
        {"connector_status": "Error", "last_error": str(exc)[:1000]},
        update_modified=True,
    )
    frappe.db.commit()
    _refresh_connected_status(account)


def _refresh_connected_status(account: str):
    child = frappe.get_doc("Meta Social Account", account)
    if not child.parent_social_account:
        return
    frappe.db.set_value(
        "Meta Connected Account",
        {"parent": child.parent_social_account, "meta_social_account": child.name},
        {"connector_status": child.connector_status, "last_sync_at": child.last_sync_at},
        update_modified=False,
    )


def enqueue_account_bootstrap(account: str, force: bool = False):
    frappe.enqueue(
        "meta_comment_ai.tasks.bootstrap_social_account",
        queue="long",
        timeout=SYNC_JOB_TIMEOUT,
        account=account,
        now=False,
        enqueue_after_commit=True,
        job_id=f"meta_comment_bootstrap_{account}_{frappe.generate_hash(length=8)}" if force else f"meta_comment_bootstrap_{account}",
        deduplicate=not force,
    )


def enqueue_account_sync(account: str):
    frappe.enqueue(
        "meta_comment_ai.tasks.sync_one_account",
        queue="long",
        timeout=SYNC_JOB_TIMEOUT,
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
        # Deduplication plus the account lock prevents recovery from racing an active job.
        enqueue_account_bootstrap(row.name)


def _is_master_token(doc) -> bool:
    return (
        doc.auth_method == "Access Token"
        and doc.access_token_mode == "User Long-Lived Token"
        and not doc.page_id
        and not doc.instagram_business_account_id
    )
