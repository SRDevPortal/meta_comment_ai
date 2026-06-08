frappe.ui.form.on("Meta Comment", {
    refresh(frm) {
        frm.add_custom_button(__("Open Inbox"), () => frappe.set_route("meta-comment-inbox"));

        if (!frm.is_new()) {
            frm.add_custom_button(__("Open Comment"), () => open_meta_comment(frm)).addClass("btn-primary");

            frm.add_custom_button(__("AI Draft"), () => {
                frappe.call({
                    method: "meta_comment_ai.api.review.generate_ai_action",
                    args: { comment_name: frm.doc.name },
                    freeze: true,
                    callback() {
                        frappe.show_alert({ message: __("AI action is ready for review."), indicator: "green" });
                        frm.reload_doc();
                    },
                });
            });

            frm.add_custom_button(__("Reply"), () => {
                frappe.prompt(
                    [{ fieldname: "reply_text", fieldtype: "Text", label: __("Reply"), reqd: 1 }],
                    (values) => {
                        frappe.call({
                            method: "meta_comment_ai.api.review.create_comment_action",
                            args: {
                                comment_name: frm.doc.name,
                                action_type: "draft_public_reply",
                                reply_text: values.reply_text,
                                execute_now: 1,
                            },
                            freeze: true,
                            callback() {
                                frm.reload_doc();
                            },
                        });
                    },
                    __("Reply to Comment")
                );
            });

            frm.add_custom_button(__("Hide"), () => create_action(frm, "hide_comment", 1));
            frm.add_custom_button(__("Delete"), () => create_action(frm, "delete_comment", 0));
        }
    },
});

function open_meta_comment(frm) {
    frappe.call({
        method: "meta_comment_ai.api.comments.get_inbox_state",
        args: { comment: frm.doc.name },
        callback(r) {
            if (r.message) {
                localStorage.setItem("meta_comment_inbox_state", JSON.stringify(r.message));
                frappe.set_route("meta-comment-inbox");
            }
        },
    });
}

function create_action(frm, action_type, execute_now) {
    frappe.call({
        method: "meta_comment_ai.api.review.create_comment_action",
        args: { comment_name: frm.doc.name, action_type, execute_now },
        freeze: true,
        callback() {
            frappe.show_alert({ message: __("Action created."), indicator: "green" });
            frm.reload_doc();
        },
    });
}
