frappe.ui.form.on("Animal", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            // ── View Buttons ──
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

            // ── Action Buttons ──
            if (frm.doc.status === "Available for Adoption") {
                frm.add_custom_button(__("Create Adoption"), function () {
                    frappe.new_doc("Adoption Application", {
                        animal: frm.doc.name, animal_name: frm.doc.animal_name,
                    });
                }, __("Actions"));
            }
            frm.add_custom_button(__("Schedule Vet Appointment"), function () {
                frappe.new_doc("Veterinary Appointment", {
                    animal: frm.doc.name, animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));
            frm.add_custom_button(__("Add Medical Record"), function () {
                frappe.new_doc("Veterinary Record", {
                    animal: frm.doc.name, animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));
            frm.add_custom_button(__("Behavior Assessment"), function () {
                frappe.new_doc("Behavior Assessment", {
                    animal: frm.doc.name, animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));
            frm.add_custom_button(__("Transfer"), function () {
                frappe.new_doc("Animal Transfer", {
                    animal: frm.doc.name, animal_name: frm.doc.animal_name,
                });
            }, __("Actions"));

            // ── Smart Kennel Recommendation ──
            frm.add_custom_button(__("Recommend Kennel"), function () {
                frappe.call({
                    method: "kennel_management.api.get_kennel_recommendations",
                    args: { animal: frm.doc.name },
                    callback: function (r) {
                        var kennels = r.message || [];
                        if (!kennels.length) {
                            frappe.msgprint(__("No suitable kennels found."));
                            return;
                        }
                        var d = new frappe.ui.Dialog({
                            title: __("Recommended Kennels for {0}", [frm.doc.animal_name]),
                            size: "large",
                        });
                        var html = '<table class="table table-bordered"><thead><tr><th>Kennel</th><th>Type</th><th>Size</th><th>Available</th><th>Match</th><th></th></tr></thead><tbody>';
                        kennels.forEach(function (k) {
                            var col = k.score >= 80 ? "#10b981" : k.score >= 60 ? "#f59e0b" : "#ef4444";
                            html += '<tr><td><strong>' + k.kennel_name + '</strong></td>';
                            html += '<td>' + (k.kennel_type || '-') + '</td>';
                            html += '<td>' + (k.size_category || '-') + '</td>';
                            html += '<td>' + k.available_spots + ' spots</td>';
                            html += '<td><span style="color:' + col + ';font-weight:700;">' + k.score + '%</span></td>';
                            html += '<td><button class="btn btn-xs btn-primary km-assign-kennel" data-kennel="' + k.name + '">Assign</button></td></tr>';
                        });
                        html += '</tbody></table>';
                        d.$body.html(html);
                        d.$body.find('.km-assign-kennel').on('click', function () {
                            frm.set_value("current_kennel", $(this).data("kennel"));
                            frm.save();
                            d.hide();
                        });
                        d.show();
                    },
                });
            }, __("Actions"));

            // ── Generate Daily Rounds ──
            frm.add_custom_button(__("Today's Rounds"), function () {
                frappe.call({
                    method: "kennel_management.api.generate_daily_rounds",
                    callback: function (r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __("{0} round(s) created for {1} occupied kennels", [r.message.created, r.message.total_kennels]),
                                indicator: r.message.created > 0 ? "green" : "blue",
                            });
                        }
                    },
                });
            }, __("Actions"));

            // ── Dashboard Indicators ──
            frm.dashboard.add_indicator(
                __("Days in Shelter: {0}", [frm.doc.__onload && frm.doc.__onload.days_in_shelter || "N/A"]),
                "blue"
            );

            // ── Long Stay Warning ──
            if (frm.doc.intake_date) {
                var days = frappe.datetime.get_diff(frappe.datetime.get_today(), frm.doc.intake_date);
                if (days > 60) {
                    frm.dashboard.add_indicator(__("⚠️ Long Stay: {0} days", [days]), "red");
                    frm.dashboard.add_comment(
                        __("This animal has been in the shelter for {0} days. Consider promoting for adoption or fostering.", [days]),
                        "yellow", true
                    );
                } else if (days > 30) {
                    frm.dashboard.add_indicator(__("📋 {0} days in shelter", [days]), "orange");
                }
            }

            // ── Health Summary Card ──
            render_health_summary(frm);
        }
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

function render_health_summary(frm) {
    frappe.call({
        method: "kennel_management.api.get_animal_health_summary",
        args: { animal: frm.doc.name },
        callback: function (r) {
            if (!r.message) return;
            var d = r.message;
            var html = '<div class="km-health-card" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-top:8px;">';
            html += '<h6 style="margin:0 0 12px;color:#334155;font-weight:600;">🏥 Health Overview</h6>';

            // Alerts
            if (d.alerts && d.alerts.length) {
                html += '<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:10px;margin-bottom:12px;">';
                d.alerts.forEach(function (a) {
                    html += '<div style="color:#dc2626;font-size:12px;">⚠️ ' + a + '</div>';
                });
                html += '</div>';
            }

            // Stats row
            html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">';

            // Next appointment
            if (d.next_appointment) {
                html += '<div style="background:white;border-radius:8px;padding:10px;text-align:center;border:1px solid #e2e8f0;">';
                html += '<div style="font-size:11px;color:#64748b;">Next Appointment</div>';
                html += '<div style="font-size:14px;font-weight:600;color:#6366f1;">' + d.next_appointment.appointment_date + '</div>';
                html += '<div style="font-size:10px;color:#94a3b8;">' + (d.next_appointment.appointment_type || '') + '</div></div>';
            } else {
                html += '<div style="background:white;border-radius:8px;padding:10px;text-align:center;border:1px solid #e2e8f0;">';
                html += '<div style="font-size:11px;color:#64748b;">Next Appointment</div>';
                html += '<div style="font-size:14px;color:#94a3b8;">None scheduled</div></div>';
            }

            // Vaccinations count
            var vaxOk = 0, vaxOverdue = 0;
            (d.vaccinations || []).forEach(function (v) {
                if (v.alert === "overdue") vaxOverdue++;
                else vaxOk++;
            });
            html += '<div style="background:white;border-radius:8px;padding:10px;text-align:center;border:1px solid #e2e8f0;">';
            html += '<div style="font-size:11px;color:#64748b;">Vaccinations</div>';
            if (vaxOverdue > 0) {
                html += '<div style="font-size:14px;font-weight:600;color:#ef4444;">' + vaxOverdue + ' overdue</div>';
            } else {
                html += '<div style="font-size:14px;font-weight:600;color:#10b981;">' + vaxOk + ' on record</div>';
            }
            html += '</div>';

            // Recent visits
            html += '<div style="background:white;border-radius:8px;padding:10px;text-align:center;border:1px solid #e2e8f0;">';
            html += '<div style="font-size:11px;color:#64748b;">Vet Visits</div>';
            html += '<div style="font-size:14px;font-weight:600;color:#334155;">' + (d.recent_visits || []).length + ' recent</div></div>';
            html += '</div>';

            // Weight trend
            if (d.weight_history && d.weight_history.length > 1) {
                html += '<div style="margin-top:8px;"><div style="font-size:11px;color:#64748b;margin-bottom:4px;">📊 Weight Trend</div>';
                html += '<div style="display:flex;align-items:end;gap:3px;height:40px;">';
                var maxW = Math.max.apply(null, d.weight_history.map(function (w) { return w.weight_kg; }));
                d.weight_history.forEach(function (w) {
                    var h = Math.max(4, Math.round((w.weight_kg / maxW) * 36));
                    html += '<div title="' + w.appointment_date + ': ' + w.weight_kg + 'kg" style="flex:1;height:' + h + 'px;background:#6366f1;border-radius:2px;"></div>';
                });
                html += '</div>';
                var last = d.weight_history[d.weight_history.length - 1];
                html += '<div style="font-size:10px;color:#94a3b8;margin-top:2px;">Latest: ' + last.weight_kg + 'kg (' + last.appointment_date + ')</div></div>';
            }

            // Recent visits list
            if (d.recent_visits && d.recent_visits.length) {
                html += '<div style="margin-top:12px;"><div style="font-size:11px;color:#64748b;margin-bottom:6px;">Recent Visits</div>';
                d.recent_visits.forEach(function (v) {
                    html += '<div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid #f1f5f9;">';
                    html += '<span style="color:#334155;">' + (v.appointment_type || 'Visit') + '</span>';
                    html += '<span style="color:#94a3b8;">' + v.appointment_date + '</span></div>';
                });
                html += '</div>';
            }

            html += '</div>';

            // Insert after the medical section
            $(frm.fields_dict.medical_section.wrapper).find(".km-health-card").remove();
            $(frm.fields_dict.medical_section.wrapper).before('<div class="km-health-card-wrap">' + html + '</div>');
        },
    });
}
