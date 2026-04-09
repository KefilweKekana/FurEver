frappe.ui.form.on("Adoption Application", {
    refresh: function (frm) {
        set_adoption_status_indicator(frm);

        // ── Compatibility Score ──
        if (!frm.is_new() && frm.doc.animal) {
            render_match_score(frm);
        }

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
            if (!frm.is_new()) render_match_score(frm);
        }
    },
});

function render_match_score(frm) {
    frappe.call({
        method: "kennel_management.api.get_adoption_match_score",
        args: { application: frm.doc.name },
        callback: function (r) {
            if (!r.message) return;
            var d = r.message;
            var color = d.score >= 80 ? "#10b981" : d.score >= 60 ? "#f59e0b" : d.score >= 40 ? "#f97316" : "#ef4444";
            var bg = d.score >= 80 ? "#ecfdf5" : d.score >= 60 ? "#fffbeb" : d.score >= 40 ? "#fff7ed" : "#fef2f2";
            var icon = d.score >= 80 ? "✅" : d.score >= 60 ? "👍" : d.score >= 40 ? "⚠️" : "❌";

            var html = '<div style="background:' + bg + ';border:1px solid ' + color + '22;border-radius:12px;padding:16px 20px;margin-bottom:15px;">';
            html += '<div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;">';
            html += '<div style="width:64px;height:64px;border-radius:50%;background:' + color + ';display:flex;align-items:center;justify-content:center;color:white;font-size:22px;font-weight:700;">' + d.score + '</div>';
            html += '<div><div style="font-size:16px;font-weight:600;color:#1f2937;">' + icon + ' Compatibility Score</div>';
            html += '<div style="color:#6b7280;font-size:13px;">' + d.summary + '</div></div></div>';
            html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">';
            (d.breakdown || []).forEach(function (b) {
                var pct = Math.round((b.points / b.max) * 100);
                var barCol = pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
                html += '<div style="font-size:12px;">';
                html += '<div style="display:flex;justify-content:space-between;margin-bottom:2px;"><span>' + b.label + '</span><span style="font-weight:600;">' + b.points + '/' + b.max + '</span></div>';
                html += '<div style="height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden;"><div style="height:100%;width:' + pct + '%;background:' + barCol + ';border-radius:3px;"></div></div>';
                html += '</div>';
            });
            html += '</div></div>';

            $(frm.fields_dict.animal_section.wrapper).find(".km-match-score").remove();
            $(frm.fields_dict.animal_section.wrapper).prepend('<div class="km-match-score">' + html + '</div>');
        },
    });
}

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
