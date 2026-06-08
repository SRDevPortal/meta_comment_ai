from __future__ import annotations

import random
import time

import frappe
from frappe.utils import add_to_date, now_datetime

from meta_comment_ai.security import require_destructive_action, require_operator
from meta_comment_ai.services import graph
from meta_comment_ai.services.policy import normalize_risk


@frappe.whitelist()
def create_comment_action(comment_name: str, action_type: str, reply_text: str | None = None, execute_now: int = 0):
    require_operator()
    comment = frappe.get_doc("Meta Comment", comment_name)
    if action_type not in {
        "draft_public_reply",
        "draft_private_reply",
        "capture_lead_and_hide",
        "hide_comment",
        "delete_comment",
        "escalate",
    }:
        frappe.throw(f"Unsupported action type: {action_type}")

    if action_type in {"draft_public_reply", "draft_private_reply"} and not (reply_text or "").strip():
        frappe.throw("Reply text is required.")
    if action_type == "delete_comment":
        require_destructive_action()

    action = frappe.get_doc(
        {
            "doctype": "Meta Comment Action",
            "meta_comment": comment.name,
            "social_account": comment.social_account,
            "action_source": "User",
            "action_type": action_type,
            "status": "Needs Review",
            "risk_level": normalize_risk(comment.risk_category),
            "reply_text": reply_text or "",
            "language": comment.language,
        }
    )
    action.insert(ignore_permissions=True)
    if int(execute_now or 0):
        return execute_action_now(action.name)
    return {"action": action.name, "status": action.status}


@frappe.whitelist()
def generate_ai_action(comment_name: str):
    require_operator()
    from meta_comment_ai.services.comments import generate_ai_recommendation_for_comment

    existing = frappe.db.get_value(
        "Meta Comment Action",
        {"meta_comment": comment_name, "action_source": "AI", "status": ["in", ["Draft", "Needs Review"]]},
        "name",
    )
    if existing:
        return {"action": existing, "status": "existing"}
    action = generate_ai_recommendation_for_comment(comment_name)
    return {"action": action, "status": "created"}


@frappe.whitelist()
def approve_action(action_name: str):
    require_operator()
    action = frappe.get_doc("Meta Comment Action", action_name)
    if action.status not in {"Draft", "Needs Review", "Failed"}:
        frappe.throw(f"Only draft, needs-review, or failed actions can be approved. Current status: {action.status}")
    if action.action_type == "delete_comment":
        require_destructive_action()

    settings = frappe.get_single("Meta Comment AI Settings")
    delay = random.randint(int(settings.min_reply_delay_seconds or 20), int(settings.max_reply_delay_seconds or 90))
    action.status = "Scheduled"
    action.approved_by = frappe.session.user
    action.approved_at = now_datetime()
    action.scheduled_for = add_to_date(now_datetime(), seconds=delay)
    action.save(ignore_permissions=True)

    frappe.enqueue(
        "meta_comment_ai.api.review.execute_approved_action",
        queue="short",
        action_name=action.name,
        delay_seconds=delay,
        enqueue_after_commit=True,
        now=False,
        job_id=f"meta_comment_action_{action.name}",
        deduplicate=True,
    )
    return {"action": action.name, "status": action.status, "scheduled_for": action.scheduled_for}


@frappe.whitelist()
def execute_action_now(action_name: str):
    require_operator()
    action = frappe.get_doc("Meta Comment Action", action_name)
    if action.status not in {"Draft", "Needs Review", "Failed", "Scheduled", "Approved"}:
        frappe.throw(f"Only draft, needs-review, failed, scheduled, or approved actions can be executed. Current status: {action.status}")
    if action.action_type == "delete_comment":
        require_destructive_action()

    action.status = "Approved"
    action.approved_by = frappe.session.user
    action.approved_at = now_datetime()
    action.scheduled_for = now_datetime()
    action.save(ignore_permissions=True)
    execute_approved_action(action.name, delay_seconds=0)
    action.reload()
    return {"action": action.name, "status": action.status, "executed_at": action.executed_at, "error": action.error}


@frappe.whitelist()
def reject_action(action_name: str, reason: str | None = None):
    require_operator()
    action = frappe.get_doc("Meta Comment Action", action_name)
    action.status = "Rejected"
    action.error = reason or "Rejected by user"
    action.save(ignore_permissions=True)
    frappe.db.set_value("Meta Comment", action.meta_comment, "processing_status", "Skipped")
    return {"action": action.name, "status": action.status}


@frappe.whitelist()
def retry_action(action_name: str):
    require_operator()
    action = frappe.get_doc("Meta Comment Action", action_name)
    action.status = "Needs Review"
    action.error = ""
    action.save(ignore_permissions=True)
    return {"action": action.name, "status": action.status}


def execute_approved_action(action_name: str, delay_seconds: int | None = None):
    if delay_seconds:
        time.sleep(max(0, min(int(delay_seconds), 120)))

    action = frappe.get_doc("Meta Comment Action", action_name)
    if action.status not in {"Approved", "Scheduled"}:
        return

    comment = frappe.get_doc("Meta Comment", action.meta_comment)
    account = frappe.get_doc("Meta Social Account", action.social_account or comment.social_account)
    settings = frappe.get_single("Meta Comment AI Settings")

    try:
        response = _execute(action, comment, account, settings)
        action.status = "Success"
        action.executed_at = now_datetime()
        action.response_json = frappe.as_json(response)
        action.meta_response_id = response.get("id") or response.get("message_id")
        action.error = ""
        action.save(ignore_permissions=True)
        _mark_comment_success(comment, action)
    except Exception as exc:
        action.status = "Failed"
        action.error = str(exc)[:1000]
        action.save(ignore_permissions=True)
        frappe.db.set_value("Meta Comment", comment.name, {"processing_status": "Failed", "last_error": str(exc)[:1000]})
        frappe.log_error(frappe.get_traceback(), "Meta Comment Action Failed")


def _execute(action, comment, account, settings):
    if action.action_type == "draft_public_reply":
        return graph.send_public_reply(account, comment.platform_comment_id, action.reply_text)
    if action.action_type == "draft_private_reply":
        if not settings.allow_private_replies:
            frappe.throw("Private replies are disabled in Meta Comment AI Settings.")
        ig_user_id = account.instagram_business_account_id or account.page_id
        return graph.send_private_reply(account, ig_user_id, comment.platform_comment_id, action.reply_text)
    if action.action_type in {"capture_lead_and_hide", "hide_comment"}:
        if settings.lead_comment_action == "Leave Visible":
            return {"success": True, "skipped": "Lead comment action is Leave Visible"}
        if settings.lead_comment_action == "Delete After Capture":
            if not settings.allow_delete_actions:
                frappe.throw("Delete action requested but delete actions are disabled.")
            return graph.delete_comment(account, comment.platform_comment_id)
        return graph.hide_comment(account, comment.platform_comment_id, hide=True)
    if action.action_type == "delete_comment":
        if not settings.allow_delete_actions:
            frappe.throw("Delete actions are disabled in Meta Comment AI Settings.")
        return graph.delete_comment(account, comment.platform_comment_id)
    if action.action_type in {"escalate", "skip"}:
        return {"success": True, "action": action.action_type}
    frappe.throw(f"Unsupported action type: {action.action_type}")


def _mark_comment_success(comment, action):
    values = {"processing_status": "Sent" if action.action_type.startswith("draft_") else "Approved", "last_error": ""}
    if action.action_type in {"capture_lead_and_hide", "hide_comment"}:
        values["hidden_on_meta"] = 1
    if action.action_type == "delete_comment":
        values["deleted_on_meta"] = 1
    if action.action_type == "escalate":
        values["processing_status"] = "Escalated"
    if action.action_type == "skip":
        values["processing_status"] = "Skipped"
    frappe.db.set_value("Meta Comment", comment.name, values)
