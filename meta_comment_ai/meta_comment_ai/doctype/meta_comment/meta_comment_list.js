frappe.listview_settings["Meta Comment"] = {
    onload(listview) {
        listview.page.add_inner_button(__("Needs Review"), () => {
            frappe.set_route("List", "Meta Comment", { processing_status: "Needs Review" });
        });
        listview.page.add_inner_button(__("Phone Leads Captured"), () => {
            frappe.set_route("List", "Meta Comment", { processing_status: "Lead Captured" });
        });
        listview.page.add_inner_button(__("Medical Escalations"), () => {
            frappe.set_route("List", "Meta Comment", { risk_category: ["in", ["Medical", "Urgent"]] });
        });
        listview.page.add_inner_button(__("Failed Meta Actions"), () => {
            frappe.set_route("List", "Meta Comment Action", { status: "Failed" });
        });
    },
    button: {
        show() {
            return true;
        },
        get_label() {
            return __("Open Comment");
        },
        get_description() {
            return __("Open this comment in Meta Comment Inbox");
        },
        action(doc) {
            frappe.call({
                method: "meta_comment_ai.api.comments.get_inbox_state",
                args: { comment: doc.name },
                freeze: true,
                freeze_message: __("Opening comment..."),
                callback(r) {
                    if (r.message) {
                        localStorage.setItem("meta_comment_inbox_state", JSON.stringify(r.message));
                        frappe.set_route("meta-comment-inbox");
                    }
                },
            });
        },
    },
};
