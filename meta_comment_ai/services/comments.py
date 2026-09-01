from __future__ import annotations

import random
from datetime import datetime

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from meta_comment_ai.services.ai import generate_recommendation
from meta_comment_ai.services.extraction import detect_language, extract_phone_numbers
from meta_comment_ai.services.leads import create_or_update_crm_lead
from meta_comment_ai.services.policy import classify_risk, normalize_risk


AUTO_SAFE_RISKS = {"Low"}
AUTO_SAFE_ACTIONS = {"draft_public_reply", "capture_lead_and_hide"}


def upsert_comment_from_event(event: dict, platform: str | None = None, account: str | None = None) -> str | None:
    normalized = normalize_event(event, platform=platform)
    comment_id = normalized.get("platform_comment_id")
    if not comment_id:
        return None

    if frappe.db.exists("Meta Comment", {"platform_comment_id": comment_id}):
        doc = frappe.get_doc("Meta Comment", {"platform_comment_id": comment_id})
        doc.raw_event_json = frappe.as_json(event)
    else:
        doc = frappe.new_doc("Meta Comment")
        doc.platform_comment_id = comment_id
        doc.platform = normalized.get("platform") or "Instagram"
        doc.social_account = account or find_account(doc.platform, normalized)
        doc.raw_event_json = frappe.as_json(event)

    for fieldname, value in normalized.items():
        if fieldname != "platform" or not doc.get("platform"):
            doc.set(fieldname, value)

    text = doc.comment_text or ""
    phones = extract_phone_numbers(text)
    doc.phone_numbers = "\n".join(phones)
    doc.language = detect_language(text)
    doc.risk_category = normalize_risk(classify_risk(text))
    doc.hide_recommended = 1 if phones else 0

    if not text.strip():
        doc.processing_status = "Unavailable"
    elif phones:
        try:
            doc.crm_lead = create_or_update_crm_lead(doc, phones)
            doc.processing_status = "Lead Captured" if doc.crm_lead else "Needs Review"
        except Exception:
            # CRM configuration must never prevent a Meta comment from being ingested.
            frappe.log_error(frappe.get_traceback(), "Meta CRM Lead Creation Failed")
            doc.processing_status = "Needs Review"
    else:
        doc.processing_status = "New"

    if not doc.is_new():
        doc._original_modified = frappe.db.get_value("Meta Comment", doc.name, "modified")
    doc.save(ignore_permissions=True)
    if not text.strip():
        return doc.name
    frappe.enqueue(
        "meta_comment_ai.services.comments.generate_ai_recommendation_for_comment",
        queue="short",
        comment_name=doc.name,
        enqueue_after_commit=True,
        now=False,
        job_id=f"meta_comment_ai_{doc.name}",
        deduplicate=True,
    )
    return doc.name


def generate_ai_recommendation_for_comment(comment_name: str) -> str | None:
    comment = frappe.get_doc("Meta Comment", comment_name)
    if not (comment.comment_text or "").strip():
        return None
    if frappe.db.exists("Meta Comment Action", {"meta_comment": comment.name, "action_source": "AI"}):
        return None

    settings = frappe.get_single("Meta Comment AI Settings")
    if settings.automation_mode == "Disabled":
        return None

    result = generate_recommendation(comment)
    action = frappe.get_doc(
        {
            "doctype": "Meta Comment Action",
            "meta_comment": comment.name,
            "social_account": comment.social_account,
            "action_source": "AI",
            "action_type": result["action"],
            "status": "Needs Review",
            "risk_level": normalize_risk(result["risk_level"]),
            "confidence": result["confidence"],
            "reply_text": result["reply_text"],
            "language": result["language"],
            "escalation_reason": result["escalation_reason"],
            "request_json": frappe.as_json({"comment": comment.as_dict()}),
            "response_json": frappe.as_json(result),
        }
    )
    action.insert(ignore_permissions=True)
    if _should_auto_execute(action, result, settings):
        _schedule_auto_action(action, settings)
        comment.processing_status = "Approved"
    else:
        comment.processing_status = "Needs Review"
    comment.hide_recommended = 1 if result.get("hide_recommended") else comment.hide_recommended
    comment.save(ignore_permissions=True)
    return action.name


def _should_auto_execute(action, result: dict, settings) -> bool:
    if settings.automation_mode != "Auto Safe Only":
        return False
    if action.action_type not in AUTO_SAFE_ACTIONS:
        return False
    if action.action_type == "capture_lead_and_hide":
        return bool(result.get("lead_phone_numbers")) and settings.lead_comment_action == "Hide After Capture"
    risk = normalize_risk(result.get("risk_level"))
    if action.action_type == "draft_public_reply":
        return risk in AUTO_SAFE_RISKS and bool((action.reply_text or "").strip())
    return False


def _schedule_auto_action(action, settings):
    delay = random.randint(int(settings.min_reply_delay_seconds or 20), int(settings.max_reply_delay_seconds or 90))
    action.status = "Scheduled"
    action.approved_by = _automation_user()
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


def _automation_user() -> str:
    return "Administrator" if frappe.db.exists("User", "Administrator") else frappe.session.user


def normalize_event(event: dict, platform: str | None = None) -> dict:
    value = _first_value(event)
    if not value:
        value = event

    comment_id = (
        value.get("comment_id")
        or value.get("id")
        or value.get("comment", {}).get("id")
        or event.get("comment_id")
        or event.get("id")
    )
    text = (
        value.get("message")
        or value.get("text")
        or value.get("comment", {}).get("text")
        or value.get("comment", {}).get("message")
        or event.get("message")
        or event.get("text")
    )
    from_obj = value.get("from") or value.get("user") or value.get("sender") or {}
    return {
        "platform": platform or _detect_platform(event),
        "platform_comment_id": str(comment_id) if comment_id else None,
        "parent_comment_id": value.get("parent_id"),
        "content_source": value.get("content_source"),
        "post_id": value.get("post_id") or value.get("post", {}).get("id"),
        "media_id": value.get("media_id") or value.get("media", {}).get("id") or value.get("source_id"),
        "ad_id": value.get("ad_id"),
        "permalink_url": value.get("permalink_url"),
        "comment_text": text or "",
        "comment_created_at": _timestamp(value),
        "commenter_id": from_obj.get("id") if isinstance(from_obj, dict) else None,
        "commenter_name": from_obj.get("name") if isinstance(from_obj, dict) else None,
        "commenter_username": value.get("username") or (from_obj.get("username") if isinstance(from_obj, dict) else None),
    }


def find_account(platform: str, normalized: dict) -> str | None:
    filters = {"platform": platform, "is_active": 1}
    account_id = normalized.get("media_id") or normalized.get("post_id")
    if platform == "Instagram" and account_id:
        rows = frappe.get_all("Meta Social Account", filters=filters, fields=["name"], limit=1)
    else:
        rows = frappe.get_all("Meta Social Account", filters=filters, fields=["name"], limit=1)
    return rows[0].name if rows else None


def _detect_platform(event: dict) -> str:
    obj = str(event.get("object") or "").lower()
    if "instagram" in obj:
        return "Instagram"
    return "Facebook"


def _first_value(event: dict) -> dict:
    for entry in event.get("entry") or []:
        changes = entry.get("changes") or []
        if changes:
            value = changes[0].get("value")
            if isinstance(value, dict):
                return value
        messaging = entry.get("messaging") or []
        if messaging and isinstance(messaging[0], dict):
            return messaging[0]
    return {}


def _timestamp(value: dict):
    return parse_meta_datetime(value.get("created_time") or value.get("timestamp"))


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
