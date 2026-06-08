from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import frappe

from meta_comment_ai.security import require_operator


@frappe.whitelist()
def get_open_comment_url(comment: str):
    require_operator()
    doc = frappe.get_doc("Meta Comment", comment)
    url = _direct_comment_url(doc)
    if not url:
        frappe.throw("No Meta URL is available for this comment yet.")
    return {"url": url}


@frappe.whitelist()
def get_inbox_state(comment: str):
    require_operator()
    doc = frappe.get_doc("Meta Comment", comment)
    return {
        "account": _parent_account(doc.social_account),
        "child_account": doc.social_account or "",
        "content_type": "All",
        "comment_filter": "All",
        "source_search": "",
        "selected_source": doc.content_source,
        "selected_comment": doc.name,
    }


def _direct_comment_url(doc) -> str | None:
    if doc.permalink_url:
        return doc.permalink_url

    source_url = _source_permalink(doc)
    if not source_url:
        return None

    if doc.platform == "Instagram":
        return _instagram_comment_url(source_url, doc.platform_comment_id)
    if doc.platform == "Facebook":
        return _facebook_comment_url(source_url, doc.platform_comment_id)
    return source_url


def _source_permalink(doc) -> str | None:
    if not doc.content_source:
        return None
    return frappe.db.get_value("Meta Content Source", doc.content_source, "permalink_url")


def _parent_account(account: str | None) -> str:
    if not account:
        return ""
    parent = frappe.db.get_value("Meta Social Account", account, "parent_social_account")
    return parent or account


def _instagram_comment_url(source_url: str, comment_id: str) -> str:
    base = source_url.split("?", 1)[0].rstrip("/")
    if not comment_id:
        return source_url
    if base.endswith(f"/c/{comment_id}"):
        return f"{base}/"
    return f"{base}/c/{comment_id}/"


def _facebook_comment_url(source_url: str, comment_id: str) -> str:
    if not comment_id:
        return source_url
    fb_comment_id = str(comment_id).split("_")[-1]
    parts = urlsplit(source_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("comment_id", fb_comment_id)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
