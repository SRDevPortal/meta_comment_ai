from __future__ import annotations

import time
from datetime import datetime

import frappe
from frappe.utils import get_datetime, now_datetime

from meta_comment_ai.security import require_operator
from meta_comment_ai.api.oauth import import_accounts
from meta_comment_ai.services import graph
from meta_comment_ai.services.comments import upsert_comment_from_event


@frappe.whitelist()
def sync_account_comments(account: str, source: str | None = None):
    require_operator()
    return _sync_account_comments(account, source=source)


def _sync_account_comments(account: str, source: str | None = None):
    doc = frappe.get_doc("Meta Social Account", account)
    source_names = []
    if source:
        source_names = [source]
    else:
        source_names = _discover_content_sources(account).get("sources") or []
        manual_source_names = ensure_manual_sources(doc)
        source_names.extend(name for name in manual_source_names if name not in source_names)

    if not source_names:
        return {
            "success": True,
            "account": account,
            "imported": 0,
            "sources": 0,
            "message": _no_source_message(doc),
        }

    imported = 0
    source_count = 0
    account_updates = {}
    try:
        for source_name in source_names:
            source_doc = frappe.get_doc("Meta Content Source", source_name)
            source_count += 1
            # Release locks before every potentially slow external request.
            frappe.db.commit()
            response = graph.list_all_comments(doc, source_doc.source_id)
            items = _comments_with_replies(doc, response.get("data") or [])
            for item in items:
                item["content_source"] = source_doc.name
                item["source_id"] = source_doc.source_id
                event = {"object": doc.platform.lower(), "entry": [{"changes": [{"value": item}]}]}
                if upsert_comment_from_event(event, platform=doc.platform, account=doc.name):
                    imported += 1
            source_doc.last_synced_at = now_datetime()
            source_doc.last_error = ""
            source_doc.save(ignore_permissions=True)
            time.sleep(0.25)
        account_updates = {"last_sync_at": now_datetime(), "last_error": "", "connector_status": "Active"}
    except Exception as exc:
        account_updates = {"last_error": str(exc)[:1000], "connector_status": "Error"}
        raise
    finally:
        if account_updates:
            frappe.db.set_value("Meta Social Account", doc.name, account_updates, update_modified=True)
    return {"success": True, "account": account, "imported": imported, "sources": source_count}


@frappe.whitelist()
def sync_source_comments(source: str):
    require_operator()
    source_doc = frappe.get_doc("Meta Content Source", source)
    if not source_doc.social_account:
        frappe.throw("This content source is not linked to a Meta Social Account.")
    return _sync_account_comments(source_doc.social_account, source=source_doc.name)


@frappe.whitelist()
def discover_content_sources(account: str, limit: int = 100):
    require_operator()
    return _discover_content_sources(account, limit=limit)


def _discover_content_sources(account: str, limit: int = 100):
    doc = frappe.get_doc("Meta Social Account", account)
    if _is_master_token_account(doc):
        token = doc.get_password("access_token")
        if not token:
            frappe.throw("Add the user access token first.")
        result = import_accounts(token, doc)
        doc.last_sync_at = now_datetime()
        doc.last_error = ""
        doc.connector_status = "Active"
        doc.save(ignore_permissions=True)
        return {
            "success": True,
            "account": account,
            "sources": [],
            "count": 0,
            "imported_accounts": result,
            "message": "Imported connected Facebook Pages and Instagram accounts. Select one of those accounts, then load posts/reels.",
        }

    names = []
    if doc.platform == "Instagram":
        frappe.db.commit()
        response = graph.list_all_instagram_media(doc, limit=min(int(limit or 100), 100))
        for item in response.get("data") or []:
            names.append(upsert_source_from_instagram(doc, item))
    else:
        frappe.db.commit()
        response = graph.list_all_facebook_posts(doc, limit=min(int(limit or 100), 100))
        for item in response.get("data") or []:
            names.append(upsert_source_from_facebook(doc, item))
    doc.last_sync_at = now_datetime()
    doc.last_error = ""
    doc.save(ignore_permissions=True)
    return {"success": True, "account": account, "sources": names, "count": len(names)}


def _comments_with_replies(account_doc, comments: list[dict]) -> list[dict]:
    """Hydrate incomplete comments and include every reply without holding DB locks."""
    result = []
    for item in comments:
        comment = dict(item)
        if not (comment.get("message") or comment.get("text")) or not (comment.get("from") or comment.get("username")):
            try:
                hydrated = graph.get_comment(account_doc, str(comment.get("id")))
                comment.update({key: value for key, value in hydrated.items() if value not in (None, "")})
            except graph.MetaGraphError:
                pass
        result.append(comment)
        comment_id = comment.get("id")
        if not comment_id:
            continue
        try:
            reply_payload = graph.list_all_replies(account_doc, str(comment_id))
        except graph.MetaGraphError:
            # Some tokens can read the top-level comment but not its replies.
            continue
        for reply in reply_payload.get("data") or []:
            reply = dict(reply)
            reply["parent_id"] = reply.get("parent_id") or str(comment_id)
            result.append(reply)
    return result


def _is_master_token_account(doc) -> bool:
    return (
        doc.auth_method == "Access Token"
        and doc.access_token_mode == "User Long-Lived Token"
        and not doc.page_id
        and not doc.instagram_business_account_id
    )


def _no_source_message(doc) -> str:
    if _is_master_token_account(doc):
        return "This is a master user-token connection. Click Load Posts/Reels first to import connected Pages/Instagram accounts, then select one of those accounts."
    return "No posts/reels were found for this account yet. Click Load Posts/Reels, or add manual source IDs in Advanced Account Data."


def ensure_manual_sources(account_doc):
    names = []
    for source_id in [row.strip() for row in (account_doc.sync_source_ids or "").splitlines() if row.strip()]:
        existing = frappe.db.get_value("Meta Content Source", {"source_id": source_id}, "name")
        if existing:
            names.append(existing)
            continue
        source = frappe.get_doc(
            {
                "doctype": "Meta Content Source",
                "source_label": f"Manual Source {source_id}",
                "platform": account_doc.platform,
                "social_account": account_doc.name,
                "source_type": "Manual Source",
                "source_id": source_id,
            }
        )
        source.insert(ignore_permissions=True)
        names.append(source.name)
    return names


def upsert_source_from_facebook(account_doc, item: dict) -> str:
    comments = item.get("comments") or {}
    summary = comments.get("summary") or {}
    return upsert_content_source(
        account_doc,
        source_id=item.get("id"),
        source_type="Facebook Post",
        label=(item.get("message") or f"Facebook Post {item.get('id')}")[:140],
        message=item.get("message"),
        permalink_url=item.get("permalink_url"),
        created_time=parse_meta_datetime(item.get("created_time")),
        comment_count=summary.get("total_count") or 0,
        raw=item,
    )


def upsert_source_from_instagram(account_doc, item: dict) -> str:
    media_type = item.get("media_type") or "MEDIA"
    source_type = "Instagram Reel" if media_type == "REELS" else "Instagram Media"
    return upsert_content_source(
        account_doc,
        source_id=item.get("id"),
        source_type=source_type,
        label=(item.get("caption") or f"{source_type} {item.get('id')}")[:140],
        message=item.get("caption"),
        permalink_url=item.get("permalink"),
        created_time=parse_meta_datetime(item.get("timestamp")),
        comment_count=item.get("comments_count") or 0,
        media_url=item.get("media_url"),
        thumbnail_url=item.get("thumbnail_url"),
        raw=item,
    )


def upsert_content_source(
    account_doc,
    *,
    source_id,
    source_type,
    label,
    message=None,
    permalink_url=None,
    created_time=None,
    comment_count=0,
    media_url=None,
    thumbnail_url=None,
    raw=None,
) -> str:
    if not source_id:
        return ""
    existing = frappe.db.get_value("Meta Content Source", {"source_id": source_id}, "name")
    doc = frappe.get_doc("Meta Content Source", existing) if existing else frappe.new_doc("Meta Content Source")
    doc.source_label = label or str(source_id)
    doc.platform = account_doc.platform
    doc.social_account = account_doc.name
    doc.source_type = source_type
    doc.source_id = source_id
    doc.message = message
    doc.permalink_url = permalink_url
    doc.created_time = created_time
    doc.comment_count = int(comment_count or 0)
    doc.media_url = media_url
    doc.thumbnail_url = thumbnail_url
    doc.raw_json = frappe.as_json(raw or {})
    doc.save(ignore_permissions=True)
    return doc.name


def parse_meta_datetime(value):
    if not value:
        return None
    text = str(value)
    for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=None)
        except Exception:
            pass
    try:
        return get_datetime(value)
    except Exception:
        text = text.replace("T", " ")
        if "+" in text:
            text = text.split("+", 1)[0]
        if text.endswith("Z"):
            text = text[:-1]
        return get_datetime(text)
