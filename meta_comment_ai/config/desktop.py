from frappe import _


def get_data():
    return [
        {
            "module_name": "Meta Comment AI",
            "category": "Modules",
            "label": _("Meta Comment AI"),
            "color": "#2f6b5f",
            "icon": "octicon octicon-comment-discussion",
            "type": "module",
            "description": _("AI-assisted Meta comment lead handling"),
        }
    ]
