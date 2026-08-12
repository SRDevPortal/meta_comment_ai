import frappe


INDEXES = (
    ("tabMeta Comment", "idx_meta_comment_parent_creation", ("parent_comment_id", "creation")),
    ("tabMeta Social Account", "idx_meta_account_page_active", ("page_id", "is_active")),
    ("tabMeta Social Account", "idx_meta_account_instagram_active", ("instagram_business_account_id", "is_active")),
    ("tabMeta Social Account", "idx_meta_account_sync_status_modified", ("is_active", "connector_status", "modified")),
)


def execute():
    for table, index_name, columns in INDEXES:
        if _index_exists(table, index_name):
            continue
        quoted_columns = ", ".join(f"`{column}`" for column in columns)
        frappe.db.sql(
            f"ALTER TABLE `{table}` ADD INDEX `{index_name}` ({quoted_columns}), "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )


def _index_exists(table: str, index_name: str) -> bool:
    return bool(
        frappe.db.sql(
            """
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND INDEX_NAME = %s
            LIMIT 1
            """,
            (table, index_name),
        )
    )
