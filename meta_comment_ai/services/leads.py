from __future__ import annotations

import frappe


def create_or_update_crm_lead(comment_doc, phone_numbers: list[str]) -> str | None:
    if not phone_numbers or not frappe.db.exists("DocType", "CRM Lead"):
        return None

    phone = phone_numbers[0]
    existing = frappe.db.get_value("CRM Lead", {"mobile_no": phone}, "name")
    if existing:
        lead = frappe.get_doc("CRM Lead", existing)
    else:
        lead = frappe.new_doc("CRM Lead")
        lead.first_name = _lead_first_name(comment_doc)
        lead.mobile_no = phone
        lead.status = _default_lead_status()

    lead.lead_name = lead.lead_name or _lead_first_name(comment_doc)
    lead.source = _ensure_lead_source(comment_doc.platform)
    if getattr(comment_doc, "social_account", None):
        owner = frappe.db.get_value("Meta Social Account", comment_doc.social_account, "default_crm_owner")
        if owner:
            lead.lead_owner = owner

    details = f"Meta comment lead from {comment_doc.platform}: {comment_doc.comment_text or ''}"
    if lead.get("details"):
        if str(comment_doc.platform_comment_id) not in str(lead.details):
            lead.details = f"{lead.details}\n\n{details}"
    else:
        lead.details = details

    lead.save(ignore_permissions=True)
    return lead.name


def _lead_first_name(comment_doc) -> str:
    return (
        comment_doc.commenter_name
        or comment_doc.commenter_username
        or f"{comment_doc.platform or 'Meta'} Comment Lead"
    )[:140]


def _default_lead_status() -> str:
    status = frappe.db.get_value("CRM Lead Status", {"name": "Lead"}, "name")
    if status:
        return status
    first_status = frappe.get_all("CRM Lead Status", pluck="name", limit=1)
    return first_status[0] if first_status else "Lead"


def _ensure_lead_source(platform: str | None) -> str | None:
    if not frappe.db.exists("DocType", "CRM Lead Source"):
        return None
    source = f"{platform or 'Meta'} Comment"
    if not frappe.db.exists("CRM Lead Source", source):
        doc = frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source})
        doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
    return source if frappe.db.exists("CRM Lead Source", source) else None
