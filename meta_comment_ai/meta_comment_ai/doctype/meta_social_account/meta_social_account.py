from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class MetaSocialAccount(Document):
    def validate(self):
        if not self.account_label:
            self.account_label = self.account_name
        if not self.account_name:
            self.account_name = self.account_label
        if not self.auth_method:
            self.auth_method = "Facebook Login"
        if not self.platform:
            self.platform = "Facebook"
        if not self.graph_api_version:
            self.graph_api_version = "v21.0"
        if not self.default_lead_source:
            self.default_lead_source = "Meta Comment"
        if self.auth_method == "Access Token" and not self.access_token_mode:
            self.access_token_mode = "User Long-Lived Token"

    def autoname(self):
        if not self.name:
            self.name = make_autoname("MSA-.#####")

    def on_update(self):
        if self.flags.get("skip_auto_sync"):
            return
        if not self.is_active or self.auth_method != "Access Token":
            return
        if not self.get_password("access_token"):
            return
        self.db_set("connector_status", "Sync Queued", update_modified=True)
        from meta_comment_ai.tasks import enqueue_account_bootstrap

        enqueue_account_bootstrap(self.name)
