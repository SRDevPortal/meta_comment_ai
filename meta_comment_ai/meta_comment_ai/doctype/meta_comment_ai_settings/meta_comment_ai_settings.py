from __future__ import annotations

from frappe.model.document import Document


class MetaCommentAISettings(Document):
    def validate(self):
        if self.min_reply_delay_seconds and self.max_reply_delay_seconds:
            if int(self.min_reply_delay_seconds) > int(self.max_reply_delay_seconds):
                self.max_reply_delay_seconds = self.min_reply_delay_seconds
