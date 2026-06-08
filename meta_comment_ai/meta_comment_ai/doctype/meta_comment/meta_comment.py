from __future__ import annotations

from frappe.model.document import Document


class MetaComment(Document):
    def before_insert(self):
        if not self.processing_status:
            self.processing_status = "New"
