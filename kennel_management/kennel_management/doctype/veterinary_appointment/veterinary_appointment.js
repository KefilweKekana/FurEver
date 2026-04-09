frappe.ui.form.on("Veterinary Appointment", {
    refresh: function (frm) {
        // Status transition buttons
        if (frm.doc.docstatus === 0) {
            if (frm.doc.status === "Scheduled") {
                frm.add_custom_button(__("Check In"), function () {
                    frm.set_value("status", "Checked In");
                    frm.save();
                }, __("Status"));

                frm.add_custom_button(__("Cancel"), function () {
                    frm.set_value("status", "Cancelled");
                    frm.save();
                }, __("Status"));

                frm.add_custom_button(__("No Show"), function () {
                    frm.set_value("status", "No Show");
                    frm.save();
                }, __("Status"));
            }

            if (frm.doc.status === "Checked In") {
                frm.add_custom_button(__("Start Examination"), function () {
                    frm.set_value("status", "In Progress");
                    frm.save();
                }, __("Status"));
            }

            if (frm.doc.status === "In Progress") {
                frm.add_custom_button(__("Complete"), function () {
                    frm.set_value("status", "Completed");
                    frm.save();
                }, __("Status"));
            }
        }

        // Quick links
        if (frm.doc.animal) {
            frm.add_custom_button(__("Animal Record"), function () {
                frappe.set_route("Form", "Animal", frm.doc.animal);
            }, __("View"));

            frm.add_custom_button(__("Medical History"), function () {
                frappe.route_options = { animal: frm.doc.animal };
                frappe.set_route("List", "Veterinary Record");
            }, __("View"));
        }
    },

    appointment_type: function (frm) {
        // Set priority based on type
        if (frm.doc.appointment_type === "Emergency") {
            frm.set_value("priority", "Emergency");
        }
    },
});
