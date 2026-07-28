import frappe
from pymysql.err import OperationalError


def execute():
    table = "tabMeta Comment"
    index_name = "idx_meta_comment_fulltext_search"
    exists = frappe.db.sql(
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
    if exists:
        return
    index_sql = (
        f"ALTER TABLE `{table}` ADD FULLTEXT INDEX `{index_name}` "
        "(`comment_text`, `commenter_name`, `commenter_username`, `phone_numbers`), "
        "ALGORITHM=INPLACE"
    )
    try:
        frappe.db.sql(f"{index_sql}, LOCK=NONE")
    except OperationalError as exc:
        if exc.args[0] != 1846:
            raise
        # MariaDB requires a shared metadata lock while building FULLTEXT indexes.
        frappe.db.sql(f"{index_sql}, LOCK=SHARED")
