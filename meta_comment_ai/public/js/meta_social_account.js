frappe.ui.form.on("Meta Social Account", {
    refresh(frm) {
        set_connection_ui(frm);

        frm.add_custom_button(__("Login with Facebook"), () => {
            if (frm.is_new()) {
                frappe.msgprint(__("Save this Meta Social Account first, then click Login with Facebook."));
                return;
            }
            if (frm.doc.auth_method !== "Facebook Login") {
                frappe.msgprint(__("Set Connection Method to Facebook Login."));
                return;
            }
            window.location.href = `/api/method/meta_comment_ai.api.oauth.begin?account=${encodeURIComponent(frm.doc.name)}`;
        }).addClass("btn-primary");

        if (!frm.is_new() && frm.doc.auth_method === "Access Token" && frm.doc.access_token) {
            frm.dashboard.set_headline(__("Automatic sync is enabled. After saving, the app imports connected Pages/Instagram accounts, loads posts/reels, and syncs comments in the background."));
        }
    },

    auth_method(frm) {
        set_connection_ui(frm);
    },

    account_label(frm) {
        if (!frm.doc.account_name && frm.doc.account_label) {
            frm.set_value("account_name", frm.doc.account_label);
        }
    },

    after_save(frm) {
        if (frm.doc.auth_method === "Access Token" && frm.doc.access_token) {
            frappe.show_alert({ message: __("Meta sync queued automatically."), indicator: "green" });
        }
    },
});

function set_connection_ui(frm) {
    const is_token = frm.doc.auth_method === "Access Token";
    const is_login = frm.doc.auth_method === "Facebook Login";

    [
        "access_token_mode",
        "access_token",
        "token_section",
    ].forEach((fieldname) => frm.toggle_display(fieldname, is_token));

    [
        "facebook_login_section",
        "meta_app_id",
        "meta_app_secret",
        "business_login_config_id",
        "oauth_redirect_uri",
        "oauth_scopes",
    ].forEach((fieldname) => frm.toggle_display(fieldname, is_login));
}
