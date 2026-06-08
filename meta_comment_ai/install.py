from __future__ import annotations

import json

import frappe


DEFAULT_SETTINGS = {
    "enable_ai_drafts": 1,
    "automation_mode": "Draft First",
    "lead_comment_action": "Hide After Capture",
    "min_reply_delay_seconds": 20,
    "max_reply_delay_seconds": 90,
    "system_prompt": (
        "You are a careful social media care coordinator for a medical clinic. "
        "Reply naturally in the same language as the comment. Vary replies like a human: "
        "sometimes plain text, sometimes short text with emoji, sometimes emoji only for light reactions. "
        "Avoid repeated templates and do not add emoji to every reply."
    ),
    "medical_guardrails": (
        "Never diagnose, prescribe, suggest medicine dosage, promise cures, or replace a clinician. "
        "For symptoms, urgent concerns, side effects, severe pain, bleeding, breathing issues, pregnancy, "
        "children, or worried medical questions, politely ask the person to contact the clinic/team."
    ),
}


def after_install():
    ensure_settings()
    ensure_workspace()
    ensure_connection_tables()


def after_migrate():
    ensure_settings()
    ensure_workspace()
    ensure_connection_tables()


def ensure_settings():
    if not frappe.db.exists("DocType", "Meta Comment AI Settings"):
        return
    settings = frappe.get_single("Meta Comment AI Settings")
    changed = False
    for fieldname, value in DEFAULT_SETTINGS.items():
        if not settings.get(fieldname):
            settings.set(fieldname, value)
            changed = True
    if not settings.get("main_social_account") and frappe.db.has_column("Meta Social Account", "parent_social_account"):
        master = _default_master_account()
        if master:
            settings.main_social_account = master
            changed = True
    if changed:
        settings.save(ignore_permissions=True)


def ensure_connection_tables():
    if not frappe.db.exists("DocType", "Meta Social Account"):
        return
    if not frappe.db.has_column("Meta Social Account", "parent_social_account"):
        return
    masters = frappe.get_all(
        "Meta Social Account",
        filters=[
            ["parent_social_account", "is", "not set"],
            ["auth_method", "in", ["Access Token", "Facebook Login"]],
        ],
        fields=["name"],
        order_by="creation asc",
    )
    if not masters:
        return
    master = masters[0].name
    children = frappe.get_all(
        "Meta Social Account",
        filters=[
            ["name", "!=", master],
            ["parent_social_account", "is", "not set"],
        ],
        fields=["name", "page_id", "instagram_business_account_id"],
    )
    for child in children:
        if child.page_id or child.instagram_business_account_id:
            frappe.db.set_value("Meta Social Account", child.name, "parent_social_account", master, update_modified=False)
    _rebuild_connected_accounts(master)


def _default_master_account():
    rows = frappe.get_all(
        "Meta Social Account",
        filters=[["parent_social_account", "is", "not set"]],
        pluck="name",
        order_by="creation asc",
        limit=1,
    )
    return rows[0] if rows else None


def _rebuild_connected_accounts(master: str):
    if not frappe.db.exists("DocType", "Meta Connected Account"):
        return
    children = frappe.get_all(
        "Meta Social Account",
        filters={"parent_social_account": master},
        fields=[
            "name",
            "account_label",
            "account_name",
            "platform",
            "connector_status",
            "page_id",
            "instagram_business_account_id",
            "last_sync_at",
        ],
        order_by="platform asc, account_label asc",
    )
    doc = frappe.get_doc("Meta Social Account", master)
    doc.connected_accounts = []
    for child in children:
        doc.append(
            "connected_accounts",
            {
                "meta_social_account": child.name,
                "account_label": child.account_label or child.account_name,
                "platform": child.platform,
                "connector_status": child.connector_status,
                "page_id": child.page_id,
                "instagram_business_account_id": child.instagram_business_account_id,
                "last_sync_at": child.last_sync_at,
            },
        )
    doc.flags.skip_auto_sync = True
    doc.save(ignore_permissions=True)


def ensure_workspace():
    if not frappe.db.exists("DocType", "Workspace"):
        return

    name = "Meta Comment AI"
    is_new = not frappe.db.exists("Workspace", name)
    if not is_new:
        workspace = frappe.get_doc("Workspace", name)
    else:
        workspace = frappe.get_doc(
            {
                "doctype": "Workspace",
                "name": name,
                "label": name,
                "title": name,
                "module": name,
                "public": 1,
                "is_standard": 1,
                "icon": "message-square",
            }
        )

    workspace.shortcuts = []
    content_blocks = [
        {
            "id": "header_main",
            "type": "header",
            "data": {"text": "Meta Comment AI", "level": 4, "col": 12},
        }
    ]
    shortcuts = [
        ("Comment Inbox", "meta-comment-inbox", "inbox", "Page"),
        ("Needs Review", "Meta Comment Action", "check-square", "DocType"),
        ("Comment Actions", "Meta Comment Action", "list", "DocType"),
        ("Comments Backup", "Meta Comment", "database"),
        ("Social Accounts", "Meta Social Account", "share-2"),
        ("AI Settings", "Meta Comment AI Settings", "settings"),
    ]
    for index, shortcut in enumerate(shortcuts):
        label, link_to, icon = shortcut[:3]
        shortcut_type = shortcut[3] if len(shortcut) > 3 else "DocType"
        workspace.append(
            "shortcuts",
            {
                "type": shortcut_type,
                "label": label,
                "link_to": link_to,
                "icon": icon,
            },
        )
        content_blocks.append(
            {
                "id": f"shortcut_{index}",
                "type": "shortcut",
                "data": {"shortcut_name": label, "col": 3},
            }
        )

    workspace.content = json.dumps(content_blocks)
    workspace.flags.ignore_links = True
    if is_new:
        workspace.insert(ignore_permissions=True, ignore_if_duplicate=True)
    else:
        workspace.save(ignore_permissions=True)
