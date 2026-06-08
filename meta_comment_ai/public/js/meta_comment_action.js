frappe.ui.form.on("Meta Comment Action", {
    refresh(frm) {
        if (["Draft", "Needs Review", "Failed"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Approve"), () => {
                frappe.call({
                    method: "meta_comment_ai.api.review.approve_action",
                    args: { action_name: frm.doc.name },
                    freeze: true,
                    callback() {
                        frm.reload_doc();
                    },
                });
            }).addClass("btn-primary");

            frm.add_custom_button(__("Reject"), () => {
                frappe.prompt(
                    [{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason") }],
                    (values) => {
                        frappe.call({
                            method: "meta_comment_ai.api.review.reject_action",
                            args: { action_name: frm.doc.name, reason: values.reason },
                            freeze: true,
                            callback() {
                                frm.reload_doc();
                            },
                        });
                    },
                    __("Reject Action")
                );
            });
        }

        if (frm.doc.status === "Failed") {
            frm.add_custom_button(__("Retry Review"), () => {
                frappe.call({
                    method: "meta_comment_ai.api.review.retry_action",
                    args: { action_name: frm.doc.name },
                    freeze: true,
                    callback() {
                        frm.reload_doc();
                    },
                });
            });
        }
    },
});
