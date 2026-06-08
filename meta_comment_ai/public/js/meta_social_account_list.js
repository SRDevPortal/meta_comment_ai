frappe.listview_settings["Meta Social Account"] = {
    filters: [["parent_social_account", "is", "not set"]],

    onload(listview) {
        apply_master_account_filter(listview);
    },

    refresh(listview) {
        apply_master_account_filter(listview);
    },
};

function apply_master_account_filter(listview) {
    const exists = (listview.filter_area.get() || []).some((filter) => {
        const fieldname = filter[1];
        const operator = filter[2];
        return fieldname === "parent_social_account" && operator === "is";
    });
    if (!exists) {
        listview.filter_area.add([["Meta Social Account", "parent_social_account", "is", "not set"]]);
    }
}
