from __future__ import annotations

import hmac
import hashlib
import json

import frappe

@frappe.whitelist(allow_guest=True)
def verify():
    args = frappe.form_dict
    mode = args.get("hub.mode")
    token = args.get("hub.verify_token")
    challenge = args.get("hub.challenge")
    if mode != "subscribe" or not challenge:
        frappe.throw("Invalid webhook verification request")
    if _verify_token(token):
        frappe.local.response.type = "text"
        return challenge
    frappe.local.response.http_status_code = 403
    return "Forbidden"


@frappe.whitelist(allow_guest=True)
def receive():
    payload = _payload()
    if not payload:
        frappe.throw("Invalid or empty Meta webhook payload")
    _verify_signature_if_configured(payload)
    frappe.enqueue(
        "meta_comment_ai.api.webhook.process_payload",
        queue="short",
        payload=payload,
        enqueue_after_commit=True,
        now=False,
        job_id=_event_job_id(payload),
        deduplicate=True,
    )
    return {"success": True, "queued": True}


def process_payload(payload: dict):
    from meta_comment_ai.services.comments import upsert_comment_from_event

    names = []
    for event, platform, account in iter_comment_events(payload):
        name = upsert_comment_from_event(event, platform=platform, account=account)
        if name:
            names.append(name)
    return names


def iter_comment_events(payload: dict):
    """Yield every event in a batched Meta webhook, not just the first change."""
    platform = "Instagram" if "instagram" in str(payload.get("object") or "").lower() else "Facebook"
    for entry in payload.get("entry") or []:
        account = _account_for_entry(platform, str(entry.get("id") or ""))
        for change in entry.get("changes") or []:
            if not isinstance(change.get("value"), dict):
                continue
            event = {"object": payload.get("object"), "entry": [{"id": entry.get("id"), "changes": [change]}]}
            yield event, platform, account
        for message in entry.get("messaging") or []:
            if not isinstance(message, dict):
                continue
            event = {"object": payload.get("object"), "entry": [{"id": entry.get("id"), "messaging": [message]}]}
            yield event, platform, account


def _account_for_entry(platform: str, entry_id: str) -> str | None:
    if not entry_id:
        return None
    fieldname = "instagram_business_account_id" if platform == "Instagram" else "page_id"
    return frappe.db.get_value("Meta Social Account", {fieldname: entry_id, "is_active": 1}, "name")


def _event_job_id(payload: dict) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_payload.encode()).hexdigest()[:16]
    return f"meta_comment_webhook_{digest}"


def _payload() -> dict:
    if frappe.request and frappe.request.data:
        try:
            return json.loads(frappe.request.data)
        except Exception:
            return {}
    return frappe.form_dict or {}


def _verify_token(token: str | None) -> bool:
    if not token:
        return False
    accounts = frappe.get_all(
        "Meta Social Account",
        filters={"is_active": 1},
        pluck="name",
        limit_page_length=1000,
    )
    for account_name in accounts:
        account = frappe.get_doc("Meta Social Account", account_name)
        if account.get_password("webhook_verify_token") == token:
            return True
    return False


def _verify_signature_if_configured(payload: dict):
    signature = frappe.get_request_header("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        frappe.throw("Missing Meta webhook signature")

    accounts = frappe.get_all(
        "Meta Social Account",
        filters={"is_active": 1},
        pluck="name",
        limit_page_length=1000,
    )
    if not accounts:
        frappe.throw("No active Meta Social Account is configured")

    raw_body = frappe.request.data or b""
    for account_name in accounts:
        secret = frappe.get_doc("Meta Social Account", account_name).get_password("webhook_secret")
        if not secret:
            continue
        expected = "sha256=" + hmac.new(secret.encode(), raw_body, "sha256").hexdigest()
        if hmac.compare_digest(signature, expected):
            return

    frappe.throw("Invalid Meta webhook signature")
