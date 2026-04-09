frappe.ui.form.on("Adoption Application", {
    refresh: function (frm) {
        set_adoption_status_indicator(frm);

        if (frm.doc.docstatus === 0) {
            // Status transitions
            if (frm.doc.status === "Pending") {
                frm.add_custom_button(__("Start Review"), function () {
                    frm.set_value("status", "Under Review");
                    frm.set_value("reviewed_by", frappe.session.user);
                    frm.set_value("review_date", frappe.datetime.nowdate());
                    frm.save();
                }, __("Actions"));
            }

            if (frm.doc.status === "Under Review") {
                frm.add_custom_button(__("Schedule Home Check"), function () {
                    frm.set_value("status", "Home Check Scheduled");
                    frm.save();
                }, __("Actions"));

                frm.add_custom_button(__("Approve"), function () {
                    frappe.confirm(
                        __("Are you sure you want to approve this application?"),
                        function () {
                            frm.set_value("status", "Approved");
                            frm.save();
                        }
                    );
                }, __("Actions"));

                frm.add_custom_button(__("Reject"), function () {
                    frappe.prompt(
                        { fieldname: "reason", label: "Rejection Reason", fieldtype: "Text", reqd: 1 },
                        function (values) {
                            frm.set_value("status", "Rejected");
                            frm.set_value("review_notes", values.reason);
                            frm.save();
                        },
                        __("Reject Application"),
                        __("Reject")
                    );
                }, __("Actions"));
            }

            if (frm.doc.status === "Approved") {
                frm.add_custom_button(__("Complete Adoption"), function () {
                    frappe.confirm(
                        __("Complete this adoption? Ensure fee is paid and contract signed."),
                        function () {
                            frm.set_value("status", "Adoption Completed");
                            if (!frm.doc.adoption_date) {
                                frm.set_value("adoption_date", frappe.datetime.nowdate());
                            }
                            frm.save_or_update();
                        }
                    );
                }, __("Actions"));
            }
        }

        // Communication shortcuts
        if (!frm.is_new() && frm.doc.email) {
            frm.add_custom_button(__("Send Email"), function () {
                new frappe.views.CommunicationComposer({
                    doc: frm.doc,
                    frm: frm,
                    subject: __("Adoption Application - {0}", [frm.doc.name]),
                    recipients: frm.doc.email,
                });
            }, __("Communications"));
        }

        if (!frm.is_new() && frm.doc.whatsapp_number) {
            frm.add_custom_button(__("Send WhatsApp"), function () {
                let url = "https://wa.me/" + frm.doc.whatsapp_number.replace(/[^0-9]/g, "");
                window.open(url, "_blank");
            }, __("Communications"));
        }

        if (!frm.is_new() && frm.doc.phone) {
            frm.add_custom_button(__("Send SMS"), function () {
                frappe.call({
                    method: "kennel_management.api.send_sms_dialog",
                    args: {
                        phone: frm.doc.phone,
                        doctype: frm.doc.doctype,
                        name: frm.doc.name,
                    },
                    callback: function (r) {
                        if (r.message) {
                            frappe.show_alert({ message: __("SMS Sent"), indicator: "green" });
                        }
                    },
                });
            }, __("Communications"));
        }
    },

    animal: function (frm) {
        if (frm.doc.animal) {
            frappe.db.get_value("Animal", frm.doc.animal, ["species", "animal_name"], function (r) {
                if (r) {
                    frm.set_value("species_preference", r.species);
                }
            });
        }
    },
});

function set_adoption_status_indicator(frm) {
    let color_map = {
        "Pending": "yellow",
        "Under Review": "blue",
        "Home Check Scheduled": "cyan",
        "Home Check Completed": "cyan",
        "Approved": "green",
        "Rejected": "red",
        "Adoption Completed": "purple",
        "Withdrawn": "grey",
        "Waitlisted": "orange",
    };
    let color = color_map[frm.doc.status] || "grey";
    frm.page.set_indicator(frm.doc.status, color);
}
