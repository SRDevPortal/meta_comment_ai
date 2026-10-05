"""Customer-number privacy for Meta comment browser and logging boundaries."""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import re

import frappe


PHONE_KEYS = frozenset({
    "customer_number",
    "customer_phone",
    "lead_phone_numbers",
    "mobile",
    "mobile_no",
    "phone",
    "phone_number",
    "phone_numbers",
})
TEXT_KEYS = frozenset({
    "account_label",
    "comment_text",
    "commenter_name",
    "commenter_username",
    "error",
    "escalation_reason",
    "last_error",
    "message",
    "reply_text",
    "source_label",
    "warning",
})
RAW_KEYS = frozenset({
    "raw_event_json",
    "request_json",
    "response_json",
})
MASKED_RE = re.compile(r"^(?:\*+[0-9]{0,4}|\[masked\])$")


def enabled() -> bool:
    return bool(frappe.conf.get("privacy_shield_desk_enabled", False)) and (
        "privacy_shield" in frappe.get_installed_apps()
    )


def restricted(user=None) -> bool:
    if not enabled():
        return False
    from privacy_shield.policy import current_capabilities

    return not current_capabilities(user).view_full


def _mask_phone_value(value):
    from privacy_shield.masking import mask_number

    if isinstance(value, list):
        return [_mask_phone_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_phone_value(item) for item in value)
    if value in (None, ""):
        return value
    if isinstance(value, str):
        lines = value.splitlines()
        if lines and all(MASKED_RE.fullmatch(line.strip()) for line in lines if line.strip()):
            return value
        if len(lines) > 1:
            return "\n".join(
                line if MASKED_RE.fullmatch(line.strip()) else mask_number(line)
                for line in lines
            )
        if MASKED_RE.fullmatch(value.strip()):
            return value
    return mask_number(value)


def project_response(payload):
    """Copy and redact custom API responses without changing stored/provider data."""
    if not restricted():
        return payload

    from privacy_shield.display_text import mask_display

    def clean(value, context=None):
        if isinstance(value, list):
            return [clean(item, context) for item in value]
        if isinstance(value, tuple):
            return tuple(clean(item, context) for item in value)
        if not isinstance(value, dict):
            if context in PHONE_KEYS:
                return _mask_phone_value(value)
            if context in TEXT_KEYS and isinstance(value, str):
                return mask_display(value)
            return deepcopy(value)

        result = {}
        for key, item in value.items():
            if key in RAW_KEYS:
                continue
            if key in PHONE_KEYS:
                result[key] = _mask_phone_value(item)
            elif key in TEXT_KEYS:
                result[key] = clean(item, key)
            else:
                result[key] = clean(item, key)
        return result

    return clean(payload)


def browser_response(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        return project_response(fn(*args, **kwargs))

    return wrapped


def mask_log_text(value):
    if not enabled() or not isinstance(value, str):
        return value
    from privacy_shield.display_text import mask_display

    return mask_display(value)


def guard_phone_search(search):
    if not search or not restricted():
        return
    from meta_comment_ai.services.extraction import extract_phone_numbers

    if extract_phone_numbers(str(search)):
        raise frappe.PermissionError(
            "Searching comments by customer phone number requires full-number visibility."
        )
