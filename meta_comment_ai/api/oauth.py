from __future__ import annotations

import secrets
from urllib.parse import quote, urlencode

import frappe
import requests
from frappe.utils import get_url

from meta_comment_ai.security import require_admin

GRAPH_BASE = "https://graph.facebook.com"
FACEBOOK_OAUTH_URL = "https://www.facebook.com/dialog/oauth"
DEFAULT_SCOPES = (
    "pages_show_list,pages_read_engagement,pages_manage_engagement,"
    "instagram_basic,instagram_manage_comments,business_management"
)


@frappe.whitelist()
def begin(account: str | None = None):
    require_admin()
    if not account:
        frappe.throw("Save the Meta Social Account first, then click Login with Facebook.")
    connector = frappe.get_doc("Meta Social Account", account)
    if connector.auth_method != "Facebook Login":
        frappe.throw("Set Connection Method to Facebook Login.")

    app_id = (connector.meta_app_id or "").strip()
    if not app_id:
        frappe.throw("Set Meta App ID in this Meta Social Account first.")

    redirect_uri = get_redirect_uri(connector)
    state = secrets.token_urlsafe(24)
    frappe.cache().set_value(_state_key(state), {"user": frappe.session.user, "account": connector.name}, expires_in_sec=900)

    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    }
    config_id = (connector.business_login_config_id or "").strip()
    if config_id:
        params.update(
            {
                "config_id": config_id,
                "override_default_response_type": "true",
                "auth_type": "rerequest",
            }
        )
    else:
        params["scope"] = _scopes(connector)
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"{FACEBOOK_OAUTH_URL}?{urlencode(params)}"


@frappe.whitelist(allow_guest=True)
def callback(code: str | None = None, state: str | None = None, error: str | None = None, error_description: str | None = None):
    code = code or frappe.form_dict.get("code")
    state = state or frappe.form_dict.get("state")
    error = error or frappe.form_dict.get("error")
    error_description = error_description or frappe.form_dict.get("error_description")
    if error:
        return _redirect_to_settings("error", error_description or error)
    if not code or not state:
        return _redirect_to_settings(
            "missing_params",
            "Open this callback through the Connect Meta button, not directly.",
        )
    state_payload = frappe.cache().get_value(_state_key(state))
    if not state_payload:
        return _redirect_to_settings(
            "invalid_state",
            "The Meta login session expired. Please try Connect Meta again.",
        )
    frappe.cache().delete_value(_state_key(state))

    account_name = state_payload.get("account") if isinstance(state_payload, dict) else None
    connector = frappe.get_doc("Meta Social Account", account_name) if account_name else None
    if not connector:
        return _redirect_to_settings("invalid_state", "Meta Social Account was not found. Please try again.")

    short_token = exchange_code_for_token(connector, code)
    long_token = exchange_for_long_lived_token(connector, short_token)
    result = import_accounts(long_token, connector)

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = (
        "/app/meta-social-account"
        f"?meta_oauth=success&facebook_pages={result['facebook_pages']}&instagram_accounts={result['instagram_accounts']}"
    )


def exchange_code_for_token(connector, code: str) -> str:
    app_id, app_secret = _credentials(connector)
    response = requests.get(
        f"{GRAPH_BASE}/{_version(connector)}/oauth/access_token",
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": get_redirect_uri(connector),
            "code": code,
        },
        timeout=30,
    )
    payload = _json_or_throw(response)
    return payload["access_token"]


def exchange_for_long_lived_token(connector, short_token: str) -> str:
    app_id, app_secret = _credentials(connector)
    response = requests.get(
        f"{GRAPH_BASE}/{_version(connector)}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    payload = _json_or_throw(response)
    return payload.get("access_token") or short_token


def import_accounts(user_access_token: str, connector=None) -> dict:
    connector = connector or _fallback_connector()
    response = requests.get(
        f"{GRAPH_BASE}/{_version(connector)}/me/accounts",
        params={
            "access_token": user_access_token,
            "fields": "id,name,category,access_token,business{id,name},instagram_business_account{id,username,name}",
            "limit": 100,
        },
        timeout=30,
    )
    payload = _json_or_throw(response)
    facebook_count = 0
    instagram_count = 0
    imported_accounts = []

    for page in payload.get("data") or []:
        page_doc = upsert_social_account(
            account_name=page.get("name") or f"Facebook Page {page.get('id')}",
            platform="Facebook",
            page_id=page.get("id"),
            instagram_business_account_id=None,
            token=page.get("access_token") or user_access_token,
            connector=connector,
            business_id=(page.get("business") or {}).get("id"),
        )
        facebook_count += 1
        imported_accounts.append(page_doc.name)

        ig = page.get("instagram_business_account") or {}
        if ig.get("id"):
            ig_doc = upsert_social_account(
                account_name=ig.get("username") or ig.get("name") or f"Instagram {ig.get('id')}",
                platform="Instagram",
                page_id=page.get("id"),
                instagram_business_account_id=ig.get("id"),
                token=page.get("access_token") or user_access_token,
                connector=connector,
                business_id=(page.get("business") or {}).get("id"),
            )
            instagram_count += 1
            imported_accounts.append(ig_doc.name)

    if connector and getattr(connector, "doctype", None) == "Meta Social Account":
        update_connected_accounts_table(connector.name, imported_accounts)

    return {
        "facebook_pages": facebook_count,
        "instagram_accounts": instagram_count,
        "accounts": imported_accounts,
    }


def upsert_social_account(
    *,
    account_name: str,
    platform: str,
    page_id: str | None,
    instagram_business_account_id: str | None,
    token: str,
    connector,
    business_id: str | None = None,
):
    filters = {"platform": platform}
    if platform == "Instagram":
        filters["instagram_business_account_id"] = instagram_business_account_id
        internal_account_name = f"instagram-{instagram_business_account_id}"
    else:
        filters["page_id"] = page_id
        internal_account_name = f"facebook-{page_id}"

    existing = frappe.db.get_value("Meta Social Account", filters, "name")
    if not existing:
        existing = frappe.db.get_value("Meta Social Account", {"account_name": internal_account_name}, "name")
    doc = frappe.get_doc("Meta Social Account", existing) if existing else frappe.new_doc("Meta Social Account")
    doc.account_name = internal_account_name
    doc.account_label = account_name
    doc.auth_method = connector.auth_method if connector else "Facebook Login"
    doc.parent_social_account = getattr(connector, "name", None) if connector and getattr(connector, "name", None) != doc.name else None
    doc.platform = platform
    doc.page_id = page_id
    doc.instagram_business_account_id = instagram_business_account_id
    doc.business_id = business_id
    doc.meta_app_id = getattr(connector, "meta_app_id", None)
    if connector and hasattr(connector, "get_password"):
        doc.meta_app_secret = connector.get_password("meta_app_secret")
    doc.business_login_config_id = getattr(connector, "business_login_config_id", None)
    doc.oauth_redirect_uri = getattr(connector, "oauth_redirect_uri", None)
    doc.oauth_scopes = getattr(connector, "oauth_scopes", None)
    doc.graph_api_version = _version(connector)
    doc.connector_status = "Active"
    doc.is_active = 1
    if not doc.default_lead_source:
        doc.default_lead_source = f"{platform} Comment"
    doc.access_token = token
    doc.save(ignore_permissions=True)
    return doc


def update_connected_accounts_table(connector_name: str, account_names: list[str]):
    connector = frappe.get_doc("Meta Social Account", connector_name)
    seen = set()
    connector.connected_accounts = []
    for name in account_names:
        if not name or name == connector.name or name in seen:
            continue
        seen.add(name)
        child = frappe.get_doc("Meta Social Account", name)
        connector.append(
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
    connector.flags.skip_auto_sync = True
    connector.save(ignore_permissions=True)


def refresh_connected_account_status(account_name: str) -> None:
    """Keep the read-only master summary in sync with its child account."""
    account = frappe.get_doc("Meta Social Account", account_name)
    if not account.parent_social_account:
        return
    frappe.db.set_value(
        "Meta Connected Account",
        {"parent": account.parent_social_account, "meta_social_account": account.name},
        {"connector_status": account.connector_status, "last_sync_at": account.last_sync_at},
        update_modified=False,
    )


def get_redirect_uri(connector=None) -> str:
    if connector and connector.oauth_redirect_uri:
        return connector.oauth_redirect_uri.strip()
    return get_url("/api/method/meta_comment_ai.api.oauth.callback")


def _credentials(connector) -> tuple[str, str]:
    app_id = (connector.meta_app_id or "").strip()
    app_secret = connector.get_password("meta_app_secret")
    if not app_id or not app_secret:
        frappe.throw("Set Meta App ID and Meta App Secret in this Meta Social Account first.")
    return app_id, app_secret


def _scopes(connector) -> str:
    return (connector.oauth_scopes or DEFAULT_SCOPES).replace("\n", ",").strip()


def _version(connector) -> str:
    return (getattr(connector, "graph_api_version", None) or "v21.0").strip().lstrip("/")


def _json_or_throw(response) -> dict:
    try:
        payload = response.json()
    except Exception:
        payload = {"error": response.text}
    if response.status_code >= 400 or payload.get("error"):
        frappe.throw(f"Meta API error: {payload.get('error') or payload}")
    return payload


def _state_key(state: str) -> str:
    return f"meta_comment_ai_oauth_state:{state}"


def _redirect_to_settings(status: str, message: str):
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = (
        "/app/meta-social-account"
        f"?meta_oauth={status}&message={quote(message)}"
    )


def _fallback_connector():
    rows = frappe.get_all("Meta Social Account", filters={"auth_method": "Facebook Login"}, fields=["name"], limit=1)
    return frappe.get_doc("Meta Social Account", rows[0].name) if rows else frappe._dict({"graph_api_version": "v21.0", "auth_method": "Access Token"})
