frappe.ui.form.on("Kennel", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            // Show animals in this kennel
            frm.add_custom_button(__("View Animals"), function () {
                frappe.route_options = { current_kennel: frm.doc.name };
                frappe.set_route("List", "Animal");
            });

            // Capacity indicator
            let occupancy_pct = frm.doc.capacity > 0
                ? Math.round((frm.doc.current_occupancy / frm.doc.capacity) * 100)
                : 0;

            let color = occupancy_pct >= 100 ? "red" : occupancy_pct >= 75 ? "orange" : "green";
            frm.dashboard.add_indicator(
                __("Occupancy: {0}/{1} ({2}%)", [frm.doc.current_occupancy, frm.doc.capacity, occupancy_pct]),
                color
            );
        }
    }
});
