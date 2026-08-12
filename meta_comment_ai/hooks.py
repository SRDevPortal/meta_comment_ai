app_name = "meta_comment_ai"
app_title = "Meta Comment AI"
app_publisher = "SAI"
app_description = "AI-assisted Facebook and Instagram comment lead handling"
app_email = "admin@example.com"
app_license = "MIT"

fixtures = [
    {"dt": "Workspace", "filters": [["module", "=", "Meta Comment AI"]]},
    {"dt": "Page", "filters": [["module", "=", "Meta Comment AI"]]},
]

after_install = "meta_comment_ai.install.after_install"
after_migrate = "meta_comment_ai.install.after_migrate"

doctype_js = {
    "Meta Comment": "public/js/meta_comment.js",
    "Meta Comment Action": "public/js/meta_comment_action.js",
    "Meta Social Account": "public/js/meta_social_account.js",
    "Meta Comment AI Settings": "public/js/meta_comment_ai_settings.js",
}

doctype_list_js = {
    "Meta Comment": "meta_comment_ai/doctype/meta_comment/meta_comment_list.js",
    "Meta Social Account": "public/js/meta_social_account_list.js",
}

scheduler_events = {
    "cron": {
        "*/15 * * * *": ["meta_comment_ai.tasks.recover_stale_syncs"],
        "0 8,20 * * *": ["meta_comment_ai.tasks.sync_recent_comments"],
    }
}
