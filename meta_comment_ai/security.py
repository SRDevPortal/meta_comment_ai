from __future__ import annotations

import frappe
from frappe import _


OPERATOR_ROLES = ("System Manager", "Sales Manager")
ADMIN_ROLES = ("System Manager",)


def require_operator():
    require_roles(OPERATOR_ROLES, _("You are not allowed to manage Meta comments."))


def require_admin():
    require_roles(ADMIN_ROLES, _("Only System Managers can manage Meta account connections."))


def require_destructive_action():
    require_roles(ADMIN_ROLES, _("Only System Managers can delete comments on Meta."))


def require_roles(roles: tuple[str, ...], message: str):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login is required."), frappe.PermissionError)
    if not any(frappe.has_role(role) for role in roles):
        frappe.throw(message, frappe.PermissionError)
