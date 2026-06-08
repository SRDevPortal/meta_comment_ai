frappe.ui.form.on("Meta Comment AI Settings", {
    refresh(frm) {
        frm.add_custom_button(__("Meta Social Accounts"), () => {
            frappe.set_route("List", "Meta Social Account");
        });
        frm.set_query("main_social_account", () => ({
            filters: { parent_social_account: ["is", "not set"] },
        }));
    },
});
