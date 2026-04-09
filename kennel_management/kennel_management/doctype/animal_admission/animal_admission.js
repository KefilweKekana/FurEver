frappe.ui.form.on("Animal Admission", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button(__("Auto-Assign Kennel"), function () {
                frappe.call({
                    method: "kennel_management.api.get_available_kennel",
                    args: {
                        species: frm.doc.species,
                        requires_quarantine: frm.doc.requires_quarantine,
                    },
                    callback: function (r) {
                        if (r.message) {
                            frm.set_value("assigned_kennel", r.message);
                            frappe.show_alert({
                                message: __("Kennel {0} auto-assigned", [r.message]),
                                indicator: "green",
                            });
                        } else {
                            frappe.show_alert({
                                message: __("No available kennels found"),
                                indicator: "red",
                            });
                        }
                    },
                });
            });
        }

        if (frm.doc.docstatus === 1 && frm.doc.animal) {
            frm.add_custom_button(__("View Animal Record"), function () {
                frappe.set_route("Form", "Animal", frm.doc.animal);
            });
        }

        // Print format
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Print Admission Form"), function () {
                frappe.utils.print(frm.doc.doctype, frm.doc.name, "SPCA Admission Form");
            });
        }
    },

    admission_type: function (frm) {
        // Toggle visibility of sections based on admission type
        let is_surrender = in_list(["Owner Surrender", "Return from Adoption", "Return from Foster"], frm.doc.admission_type);
        let is_stray = in_list(["Stray", "Rescue", "Confiscation"], frm.doc.admission_type);

        frm.toggle_reqd("surrendered_by_name", is_surrender);
        frm.toggle_reqd("surrender_reason", frm.doc.admission_type === "Owner Surrender");
        frm.toggle_reqd("found_location", is_stray);
    },

    species: function (frm) {
        // Auto-suggest quarantine for certain admission types
        if (in_list(["Stray", "Rescue", "Confiscation"], frm.doc.admission_type)) {
            frm.set_value("requires_quarantine", 1);
        }
    },

    requires_quarantine: function (frm) {
        if (frm.doc.requires_quarantine && !frm.doc.quarantine_end_date) {
            // Default quarantine period: 10 days
            let end_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 10);
            frm.set_value("quarantine_end_date", end_date);
        }
    },
});
