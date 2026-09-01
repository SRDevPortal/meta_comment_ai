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
    source_field = frappe.get_meta("CRM Lead").get_field("source")
    source_doctype = (source_field.options or "").strip() if source_field else ""
    if not source_doctype or not frappe.db.exists("DocType", source_doctype):
        return None

    source = f"{platform or 'Meta'} Comment"
    if frappe.db.exists(source_doctype, source):
        return source

    meta = frappe.get_meta(source_doctype)
    values = {"doctype": source_doctype}
    for fieldname in ("source_name", meta.title_field, "title"):
        if fieldname and meta.has_field(fieldname):
            values[fieldname] = source
            break

    try:
        frappe.get_doc(values).insert(ignore_permissions=True, ignore_if_duplicate=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Could not create Meta lead source in {source_doctype}")

    return source if frappe.db.exists(source_doctype, source) else None
