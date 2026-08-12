from __future__ import annotations

import frappe
from frappe.utils import getdate

from meta_comment_ai.security import require_operator

MAX_COMMENT_PAGE_SIZE = 200
MAX_SOURCE_PAGE_SIZE = 1000
REPLY_ACTION_TYPES = ("draft_public_reply", "draft_private_reply")
REPLY_STATUSES = ("Draft", "Needs Review", "Approved", "Scheduled", "Success")


@frappe.whitelist()
def get_accounts():
    require_operator()
    rows = frappe.get_all(
        "Meta Social Account",
        filters=[["parent_social_account", "is", "not set"]],
        fields=[
            "name",
            "account_label",
            "platform",
            "connector_status",
            "is_active",
            "auth_method",
            "access_token_mode",
            "page_id",
            "instagram_business_account_id",
        ],
        order_by="platform asc, account_label asc, name asc",
        limit_page_length=MAX_SOURCE_PAGE_SIZE,
    )
    connected_counts = {
        row.parent_social_account: row.count
        for row in frappe.get_all(
            "Meta Social Account",
            filters={"parent_social_account": ["is", "set"]},
            fields=["parent_social_account", "count(name) as count"],
            group_by="parent_social_account",
            limit_page_length=MAX_SOURCE_PAGE_SIZE,
        )
    }
    for row in rows:
        row["connected_count"] = connected_counts.get(row.name, 0)
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
            "account_label",
            "platform",
            "connector_status",
            "page_id",
            "instagram_business_account_id",
        ],
        order_by="platform asc, account_label asc, name asc",
        limit_page_length=MAX_SOURCE_PAGE_SIZE,
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
    metrics = _source_comment_metrics(source_names)
    for row in rows:
        counts = metrics.get(row.name, {})
        row["account_label"] = account_labels.get(row.social_account, row.social_account)
        row["imported_comment_count"] = counts.get("imported_count", 0)
        row["open_comment_count"] = counts.get("open_count", 0)
        row["needs_review_count"] = counts.get("needs_review_count", 0)
        row["lead_count"] = counts.get("lead_count", 0)
        row["failed_count"] = counts.get("failed_count", 0)
        row["sent_count"] = counts.get("sent_count", 0)
        row["no_reply_count"] = counts.get("no_reply_count", 0)

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
    before_creation: str | None = None,
):
    require_operator()
    limit = max(1, min(int(limit or 50), MAX_COMMENT_PAGE_SIZE))
    filters = {}
    if child_account:
        filters["social_account"] = child_account
    elif account:
        filters["social_account"] = ["in", _account_scope(account)]
    if source:
        filters["content_source"] = source
    if status and status != "All":
        filters["processing_status"] = status
    if before_creation:
        filters["creation"] = ["<", before_creation]

    if search:
        matching_names = _search_comment_names(search, filters, limit)
        if not matching_names:
            return []
        filters["name"] = ["in", matching_names]

    rows = frappe.get_all(
        "Meta Comment",
        filters=filters,
        fields=[
            "name",
            "platform",
            "social_account",
            "processing_status",
            "risk_category",
            "platform_comment_id",
            "parent_comment_id",
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
        order_by="creation desc",
        limit=limit,
    )
    account_labels = _account_labels()
    source_labels = _source_labels()
    actions_by_comment, replied_comments = _actions_for_comments([row.name for row in rows])
    for row in rows:
        row["account_label"] = account_labels.get(row.social_account, row.social_account)
        row["source_label"] = source_labels.get(row.content_source, row.content_source)
        row["actions"] = actions_by_comment.get(row.name, [])
        row["has_reply"] = row.name in replied_comments
    if comment_filter == "No Reply":
        rows = [row for row in rows if not row.get("has_reply")]
    return rows


def _search_comment_names(search: str, filters: dict, limit: int) -> list[str]:
    conditions = [
        "MATCH(comment_text, commenter_name, commenter_username, phone_numbers) "
        "AGAINST (%(search)s IN BOOLEAN MODE)"
    ]
    params = {"search": _boolean_search(search), "limit": limit}
    for fieldname in ("social_account", "content_source", "processing_status"):
        value = filters.get(fieldname)
        if not value:
            continue
        if isinstance(value, list) and value[0] == "in":
            conditions.append(f"`{fieldname}` IN %({fieldname})s")
            params[fieldname] = tuple(value[1])
        else:
            conditions.append(f"`{fieldname}` = %({fieldname})s")
            params[fieldname] = value
    rows = frappe.db.sql(
        f"""
        SELECT name
        FROM `tabMeta Comment`
        WHERE {" AND ".join(conditions)}
        ORDER BY comment_created_at DESC, creation DESC
        LIMIT %(limit)s
        """,
        params,
        pluck=True,
    )
    return rows


def _boolean_search(search: str) -> str:
    terms = [term for term in search.strip().split() if term]
    return " ".join(f"+{term}*" for term in terms)


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
            limit_page_length=100,
        ),
    }


def _ensure_ai_suggestion(comment_name: str):
    if frappe.db.exists("Meta Comment Action", {"meta_comment": comment_name, "action_source": "AI"}):
        return
    from meta_comment_ai.services.comments import generate_ai_recommendation_for_comment

    generate_ai_recommendation_for_comment(comment_name)


def _account_labels():
    return {
        row.name: row.account_label or row.name
        for row in frappe.get_all(
            "Meta Social Account",
            fields=["name", "account_label"],
            limit_page_length=MAX_SOURCE_PAGE_SIZE,
        )
    }


def _account_scope(account: str) -> list[str]:
    children = frappe.get_all(
        "Meta Social Account",
        filters={"parent_social_account": account},
        pluck="name",
        limit_page_length=MAX_SOURCE_PAGE_SIZE,
    )
    return [account] + children


def _source_labels():
    return {
        row.name: row.source_label or row.name
        for row in frappe.get_all(
            "Meta Content Source",
            fields=["name", "source_label"],
            limit_page_length=MAX_SOURCE_PAGE_SIZE,
        )
    }


def _comment_counts(sources: list[str], statuses: list[str] | None = None) -> dict[str, int]:
    if not sources:
        return {}
    filters = {"content_source": ["in", sources]}
    if statuses:
        filters["processing_status"] = ["in", statuses]
    rows = frappe.get_all(
        "Meta Comment",
        filters=filters,
        fields=["content_source", "count(name) as count"],
        group_by="content_source",
    )
    return {row.content_source: row.count for row in rows}


def _source_comment_metrics(sources: list[str]) -> dict[str, dict]:
    if not sources:
        return {}
    rows = frappe.db.sql(
        """
        SELECT
            c.content_source,
            COUNT(c.name) AS imported_count,
            SUM(c.processing_status IN ('New', 'Needs Review', 'Lead Captured', 'Escalated', 'Failed')) AS open_count,
            SUM(c.processing_status = 'Needs Review') AS needs_review_count,
            COUNT(NULLIF(c.phone_numbers, '')) AS lead_count,
            SUM(c.processing_status = 'Failed') AS failed_count,
            SUM(c.processing_status = 'Sent') AS sent_count,
            SUM(NOT EXISTS (
                SELECT 1
                FROM `tabMeta Comment Action` a
                WHERE a.meta_comment = c.name
                  AND a.action_type IN %(action_types)s
                  AND a.status IN %(statuses)s
            )) AS no_reply_count
        FROM `tabMeta Comment` c
        WHERE c.content_source IN %(sources)s
        GROUP BY c.content_source
        """,
        {
            "sources": tuple(sources),
            "action_types": REPLY_ACTION_TYPES,
            "statuses": REPLY_STATUSES,
        },
        as_dict=True,
    )
    return {row.content_source: row for row in rows}


def _actions_for_comments(comment_names: list[str]) -> tuple[dict[str, list], set[str]]:
    if not comment_names:
        return {}, set()
    rows = frappe.db.sql(
        """
        SELECT name, meta_comment, action_type, status, reply_text,
               risk_level, confidence, creation
        FROM (
            SELECT name, meta_comment, action_type, status, reply_text,
                   risk_level, confidence, creation,
                   ROW_NUMBER() OVER (
                       PARTITION BY meta_comment ORDER BY creation DESC
                   ) AS row_number
            FROM `tabMeta Comment Action`
            WHERE meta_comment IN %(comment_names)s
        ) ranked_actions
        WHERE row_number <= 5
        ORDER BY creation DESC
        """,
        {"comment_names": tuple(comment_names)},
        as_dict=True,
    )
    replied_rows = frappe.get_all(
        "Meta Comment Action",
        filters={
            "meta_comment": ["in", comment_names],
            "action_type": ["in", REPLY_ACTION_TYPES],
            "status": ["in", REPLY_STATUSES],
        },
        fields=["meta_comment"],
        group_by="meta_comment",
        limit_page_length=len(comment_names),
    )
    actions_by_comment = {}
    for row in rows:
        actions_by_comment.setdefault(row.meta_comment, []).append(row)
    replied_comments = {row.meta_comment for row in replied_rows}
    return actions_by_comment, replied_comments


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
