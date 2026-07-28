import frappe

from meta_comment_ai.patches.v0_0.add_inbox_indexes import _index_exists


def execute():
    table = "tabMeta Comment"
    index_name = "idx_meta_comment_account_status_creation"
    if _index_exists(table, index_name):
        return
    frappe.db.sql(
        f"ALTER TABLE `{table}` ADD INDEX `{index_name}` "
        "(`social_account`, `processing_status`, `creation`), "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )
