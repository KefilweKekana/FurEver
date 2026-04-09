frappe.ui.form.on("Animal", {
    refresh: function (frm) {
        // Custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__("Medical History"), function () {
                frappe.route_options = { animal: frm.doc.name };
                frappe.set_route("List", "Veterinary Record");
            }, __("View"));

            frm.add_custom_button(__("Appointments"), function () {
                frappe.route_options = { animal: frm.doc.name };
                frappe.set_route("List", "Veterinary Appointment");
            }, __("View"));

            frm.add_custom_button(__("Behavior Assessments"), function () {
                frappe.route_options = { animal: frm.doc.name };
                frappe.set_route("List", "Behavior Assessment");
            }, __("View"));

            // Action buttons based on status
            if (frm.doc.status === "Available for Adoption") {
                frm.add_custom_button(__("Create Adoption"), function () {
                    frappe.new_doc("Adoption Application", {
                        animal: frm.doc.name,
                        animal_name: frm.doc.animal_name,
                    });
                }, __("Actions"));
            }

            frm.add_custom_button(__("Schedule Vet Appointment"), function () {
                frappe.new_doc("Veterinary Appointment", {
                    animal: frm.doc.name,
                    animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Add Medical Record"), function () {
                frappe.new_doc("Veterinary Record", {
                    animal: frm.doc.name,
                    animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Behavior Assessment"), function () {
                frappe.new_doc("Behavior Assessment", {
                    animal: frm.doc.name,
                    animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Transfer"), function () {
                frappe.new_doc("Animal Transfer", {
                    animal: frm.doc.name,
                    animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));

            // Dashboard indicators
            frm.dashboard.add_indicator(
                __("Days in Shelter: {0}", [frm.doc.__onload && frm.doc.__onload.days_in_shelter || "N/A"]),
                "blue"
            );
        }

        // Set status indicator color
        set_status_indicator(frm);
    },

    species: function (frm) {
        // Show/hide species-specific fields
        frm.toggle_display("fiv_felv_status", frm.doc.species === "Cat");
        frm.toggle_display("heartworm_status", frm.doc.species === "Dog");
    },

    weight_kg: function (frm) {
        if (frm.doc.weight_kg && frm.doc.species === "Dog") {
            let weight = frm.doc.weight_kg;
            let size = "";
            if (weight < 5) size = "Tiny (< 5kg)";
            else if (weight < 10) size = "Small (5-10kg)";
            else if (weight < 25) size = "Medium (10-25kg)";
            else if (weight < 45) size = "Large (25-45kg)";
            else size = "Giant (> 45kg)";
            frm.set_value("size", size);
        }
    },

    date_of_birth: function (frm) {
        if (frm.doc.date_of_birth) {
            let dob = frappe.datetime.str_to_obj(frm.doc.date_of_birth);
            let now = new Date();
            let diff = now - dob;
            let days = Math.floor(diff / (1000 * 60 * 60 * 24));
            frm.set_value("estimated_age_years", Math.floor(days / 365));
            frm.set_value("estimated_age_months", Math.floor((days % 365) / 30));
        }
    },
});

function set_status_indicator(frm) {
    let color_map = {
        "Available for Adoption": "green",
        "Adopted": "purple",
        "In Foster Care": "blue",
        "Medical Hold": "red",
        "Behavior Hold": "red",
        "Quarantine": "orange",
        "Stray Hold": "yellow",
        "In Treatment": "orange",
        "Reserved": "cyan",
        "Transferred": "grey",
        "Deceased": "darkgrey",
        "Returned to Owner": "blue",
    };
    let color = color_map[frm.doc.status] || "grey";
    frm.page.set_indicator(frm.doc.status, color);
}
