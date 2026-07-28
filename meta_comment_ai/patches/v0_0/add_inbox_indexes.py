import frappe


INDEXES = (
    (
        "tabMeta Comment",
        "idx_meta_comment_account_status_created",
        ("social_account", "processing_status", "comment_created_at", "creation"),
    ),
    (
        "tabMeta Comment",
        "idx_meta_comment_source_status",
        ("content_source", "processing_status"),
    ),
    (
        "tabMeta Comment",
        "idx_meta_comment_account_status_creation",
        ("social_account", "processing_status", "creation"),
    ),
    (
        "tabMeta Comment Action",
        "idx_meta_action_comment_creation",
        ("meta_comment", "creation"),
    ),
    (
        "tabMeta Comment Action",
        "idx_meta_action_reply_status_comment",
        ("action_type", "status", "meta_comment"),
    ),
    (
        "tabMeta Social Account",
        "idx_meta_account_parent_active",
        ("parent_social_account", "is_active"),
    ),
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
