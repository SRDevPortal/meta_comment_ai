from __future__ import annotations

import frappe

from meta_comment_ai.security import require_admin, require_operator
from meta_comment_ai.api.oauth import import_accounts
from meta_comment_ai.services import graph


@frappe.whitelist()
def import_from_access_token(account: str | None = None, access_token: str | None = None):
    """Import connected Page/Instagram accounts from a user token, or validate one page token."""
    require_admin()
    if account:
        doc = frappe.get_doc("Meta Social Account", account)
        token = doc.get_password("access_token")
        if not token:
            frappe.throw("Add an access token first.")

        if doc.access_token_mode == "User Long-Lived Token":
            return import_accounts(token, doc)

        if not doc.page_id and not doc.instagram_business_account_id:
            frappe.throw("For Page Access Token, add Page ID or Instagram Business Account ID before testing.")

        target_id = doc.instagram_business_account_id or doc.page_id
        payload = graph.get_object(doc, target_id, fields="id,name,username")
        doc.connector_status = "Active"
        doc.last_error = ""
        if payload.get("name") and not doc.account_label:
            doc.account_label = payload.get("name")
        doc.save(ignore_permissions=True)
        return {"success": True, "account": doc.name, "meta_object": payload}

    if not access_token:
        frappe.throw("Access token is required.")
    return import_accounts(access_token)


@frappe.whitelist()
def get_connection_help():
    require_operator()
    return {
        "facebook_login": "Use this for production multi-account setup. One Meta app can connect many Facebook users/businesses.",
        "access_token": "Use this when you already have a long-lived user token or page token. User tokens can import all accessible Pages; page tokens validate one account.",
    }


@frappe.whitelist()
def start_background_sync(account: str | None = None):
    require_operator()
    from meta_comment_ai.tasks import enqueue_account_bootstrap

    if account:
        enqueue_account_bootstrap(account)
        return {"queued": 1, "accounts": [account]}

    accounts = frappe.get_all(
        "Meta Social Account",
        filters={"is_active": 1, "parent_social_account": ["is", "not set"]},
        pluck="name",
    )
    for name in accounts:
        enqueue_account_bootstrap(name)
    return {"queued": len(accounts), "accounts": accounts}
