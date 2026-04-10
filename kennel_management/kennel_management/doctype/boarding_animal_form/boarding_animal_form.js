frappe.ui.form.on("Boarding Animal Form", {
    refresh: function(frm) {
        // Print button to see the SPCA form layout
        if (!frm.is_new()) {
            frm.add_custom_button(__("Print SPCA Form"), function() {
                window.open(
                    frappe.urllib.get_full_url(
                        "/api/method/frappe.utils.print_format.download_pdf?"
                        + "doctype=Boarding+Animal+Form&name=" + frm.doc.name
                        + "&format=Tshwane+SPCA+Boarding+Form"
                    ),
                    "_blank"
                );
            }, __("Actions"));
        }
    },

    date_in: function(frm) { frm.trigger("calc_total"); },
    date_out: function(frm) { frm.trigger("calc_total"); },
    cost_per_day: function(frm) { frm.trigger("calc_total"); },
    amount_paid: function(frm) {
        frm.set_value("outstanding", flt(frm.doc.total_cost) - flt(frm.doc.amount_paid));
    },

    calc_total: function(frm) {
        if (frm.doc.date_in && frm.doc.date_out && frm.doc.cost_per_day) {
            var days = frappe.datetime.get_diff(frm.doc.date_out, frm.doc.date_in);
            if (days < 1) days = 1;
            frm.set_value("total_cost", flt(frm.doc.cost_per_day) * days);
            frm.set_value("outstanding", flt(frm.doc.total_cost) - flt(frm.doc.amount_paid));
        }
    }
});
