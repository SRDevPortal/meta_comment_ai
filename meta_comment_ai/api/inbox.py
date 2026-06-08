from __future__ import annotations

import frappe
from frappe.utils import getdate

from meta_comment_ai.security import require_operator


@frappe.whitelist()
def get_accounts():
    require_operator()
    rows = frappe.get_all(
        "Meta Social Account",
        filters=[["parent_social_account", "is", "not set"]],
        fields=[
            "name",
            "account_name",
            "account_label",
            "platform",
            "connector_status",
            "is_active",
            "auth_method",
            "access_token_mode",
            "page_id",
            "instagram_business_account_id",
        ],
        order_by="platform asc, account_label asc, account_name asc",
    )
    for row in rows:
        row["connected_count"] = frappe.db.count("Meta Social Account", {"parent_social_account": row.name})
        row["can_sync"] = bool(row.page_id or row.instagram_business_account_id)
        row["is_master_connection"] = bool(
            row.auth_method == "Access Token"
            and row.access_token_mode == "User Long-Lived Token"
            and not row.can_sync
        )
    return rows


@frappe.whitelist()
def get_connected_accounts(account: str | None = None):
    require_operator()
    if not account:
        return []
    return frappe.get_all(
        "Meta Social Account",
        filters={"parent_social_account": account, "is_active": 1},
        fields=[
            "name",
            "account_name",
            "account_label",
            "platform",
            "connector_status",
            "page_id",
            "instagram_business_account_id",
        ],
        order_by="platform asc, account_label asc, account_name asc",
    )


@frappe.whitelist()
def get_sources(
    account: str | None = None,
    child_account: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    comment_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    require_operator()
    filters = {}
    if child_account:
        filters["social_account"] = child_account
    elif account:
        filters["social_account"] = ["in", _account_scope(account)]
    if platform and platform != "All":
        filters["platform"] = platform
    if content_type and content_type != "All":
        if content_type == "Reels":
            filters["source_type"] = "Instagram Reel"
        elif content_type == "Posts":
            filters["source_type"] = ["in", ["Facebook Post", "Instagram Media"]]
    if date_from:
        filters["created_time"] = [">=", f"{getdate(date_from)} 00:00:00"]
    if date_to:
        filters.setdefault("created_time", ["<=", f"{getdate(date_to)} 23:59:59"])
        if isinstance(filters["created_time"], list) and filters["created_time"][0] == ">=":
            filters["created_time"] = ["between", [f"{getdate(date_from)} 00:00:00", f"{getdate(date_to)} 23:59:59"]]

    rows = frappe.get_all(
        "Meta Content Source",
        filters=filters,
        fields=[
            "name",
            "source_label",
            "platform",
            "social_account",
            "source_type",
            "source_id",
            "message",
            "permalink_url",
            "created_time",
            "media_url",
            "thumbnail_url",
            "comment_count",
            "last_synced_at",
        ],
        order_by="created_time desc, modified desc",
        limit=1000,
    )

    account_labels = _account_labels()
    source_names = [row.name for row in rows]
    imported_counts = _comment_counts(source_names)
    open_counts = _comment_counts(source_names, statuses=["New", "Needs Review", "Lead Captured", "Escalated", "Failed"])
    needs_review_counts = _comment_counts(source_names, statuses=["Needs Review"])
    lead_counts = _comment_counts(source_names, phone_only=True)
    failed_counts = _comment_counts(source_names, statuses=["Failed"])
    sent_counts = _comment_counts(source_names, statuses=["Sent"])
    no_reply_counts = _no_reply_counts(source_names)
    for row in rows:
        row["account_label"] = account_labels.get(row.social_account, row.social_account)
        row["imported_comment_count"] = imported_counts.get(row.name, 0)
        row["open_comment_count"] = open_counts.get(row.name, 0)
        row["needs_review_count"] = needs_review_counts.get(row.name, 0)
        row["lead_count"] = lead_counts.get(row.name, 0)
        row["failed_count"] = failed_counts.get(row.name, 0)
        row["sent_count"] = sent_counts.get(row.name, 0)
        row["no_reply_count"] = no_reply_counts.get(row.name, 0)

    if comment_filter and comment_filter != "All":
        rows = [row for row in rows if _source_matches_comment_filter(row, comment_filter)]
    return rows


@frappe.whitelist()
def get_source_detail(source: str):
    require_operator()
    doc = frappe.get_doc("Meta Content Source", source)
    account_labels = _account_labels()
    return {
        "source": {
            **doc.as_dict(),
            "account_label": account_labels.get(doc.social_account, doc.social_account),
            "imported_comment_count": frappe.db.count("Meta Comment", {"content_source": doc.name}),
        },
        "comments": get_comments(account=doc.social_account, source=doc.name, limit=1000),
    }


@frappe.whitelist()
def get_comments(
    account: str | None = None,
    child_account: str | None = None,
    source: str | None = None,
    status: str | None = None,
    comment_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
):
    require_operator()
    filters = {}
    if child_account:
        filters["social_account"] = child_account
    elif account:
        filters["social_account"] = ["in", _account_scope(account)]
    if source:
        filters["content_source"] = source
    if status and status != "All":
        filters["processing_status"] = status

    or_filters = None
    if search:
        or_filters = [
            ["Meta Comment", "comment_text", "like", f"%{search}%"],
            ["Meta Comment", "commenter_name", "like", f"%{search}%"],
            ["Meta Comment", "commenter_username", "like", f"%{search}%"],
            ["Meta Comment", "phone_numbers", "like", f"%{search}%"],
        ]

    rows = frappe.get_all(
        "Meta Comment",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "platform",
            "social_account",
            "processing_status",
            "risk_category",
            "platform_comment_id",
            "content_source",
            "comment_text",
            "language",
            "comment_created_at",
            "commenter_name",
            "commenter_username",
            "phone_numbers",
            "crm_lead",
            "hidden_on_meta",
            "deleted_on_meta",
            "permalink_url",
            "creation",
        ],
        order_by="comment_created_at desc, creation desc",
        limit=int(limit or 50),
    )
    account_labels = _account_labels()
    source_labels = _source_labels()
    for row in rows:
        row["account_label"] = account_labels.get(row.social_account, row.social_account)
        row["source_label"] = source_labels.get(row.content_source, row.content_source)
        row["actions"] = frappe.get_all(
            "Meta Comment Action",
            filters={"meta_comment": row.name},
            fields=["name", "action_type", "status", "reply_text", "risk_level", "confidence", "creation"],
            order_by="creation desc",
            limit=5,
        )
        row["has_reply"] = _comment_has_reply(row.name)
    if comment_filter == "No Reply":
        rows = [row for row in rows if not row.get("has_reply")]
    return rows


@frappe.whitelist()
def get_comment_detail(comment: str):
    require_operator()
    doc = frappe.get_doc("Meta Comment", comment)
    _ensure_ai_suggestion(doc.name)
    doc.reload()
    return {
        "comment": doc.as_dict(),
        "actions": frappe.get_all(
            "Meta Comment Action",
            filters={"meta_comment": doc.name},
            fields=[
                "name",
                "action_source",
                "action_type",
                "status",
                "reply_text",
                "language",
                "risk_level",
                "confidence",
                "error",
                "creation",
                "executed_at",
            ],
            order_by="creation desc",
        ),
    }


def _ensure_ai_suggestion(comment_name: str):
    if frappe.db.exists("Meta Comment Action", {"meta_comment": comment_name, "action_source": "AI"}):
        return
    from meta_comment_ai.services.comments import generate_ai_recommendation_for_comment

    generate_ai_recommendation_for_comment(comment_name)


def _account_labels():
    return {
        row.name: row.account_label or row.account_name or row.name
        for row in frappe.get_all("Meta Social Account", fields=["name", "account_name", "account_label"])
    }


def _account_scope(account: str) -> list[str]:
    children = frappe.get_all("Meta Social Account", filters={"parent_social_account": account}, pluck="name")
    return [account] + children


def _source_labels():
    return {
        row.name: row.source_label or row.name
        for row in frappe.get_all("Meta Content Source", fields=["name", "source_label"])
    }


def _comment_counts(sources: list[str], statuses: list[str] | None = None, phone_only: bool = False) -> dict[str, int]:
    if not sources:
        return {}
    filters = {"content_source": ["in", sources]}
    if statuses:
        filters["processing_status"] = ["in", statuses]
    if phone_only:
        filters["phone_numbers"] = ["!=", ""]
    rows = frappe.get_all(
        "Meta Comment",
        filters=filters,
        fields=["content_source", "count(name) as count"],
        group_by="content_source",
    )
    return {row.content_source: row.count for row in rows}


def _no_reply_counts(sources: list[str]) -> dict[str, int]:
    if not sources:
        return {}
    replied = frappe.get_all(
        "Meta Comment Action",
        filters={
            "action_type": ["in", ["draft_public_reply", "draft_private_reply"]],
            "status": ["in", ["Draft", "Needs Review", "Approved", "Scheduled", "Success"]],
        },
        pluck="meta_comment",
    )
    filters = {"content_source": ["in", sources]}
    if replied:
        filters["name"] = ["not in", replied]
    rows = frappe.get_all(
        "Meta Comment",
        filters=filters,
        fields=["content_source", "count(name) as count"],
        group_by="content_source",
    )
    return {row.content_source: row.count for row in rows}


def _comment_has_reply(comment: str) -> bool:
    return bool(
        frappe.db.exists(
            "Meta Comment Action",
            {
                "meta_comment": comment,
                "action_type": ["in", ["draft_public_reply", "draft_private_reply"]],
                "status": ["in", ["Draft", "Needs Review", "Approved", "Scheduled", "Success"]],
            },
        )
    )


def _source_matches_comment_filter(row, comment_filter: str) -> bool:
    if comment_filter == "No Reply":
        return bool(row.get("no_reply_count"))
    if comment_filter == "Needs Review":
        return bool(row.get("needs_review_count"))
    if comment_filter == "Lead Captured":
        return bool(row.get("lead_count"))
    if comment_filter == "Failed":
        return bool(row.get("failed_count"))
    if comment_filter == "Sent":
        return bool(row.get("sent_count"))
    return True
