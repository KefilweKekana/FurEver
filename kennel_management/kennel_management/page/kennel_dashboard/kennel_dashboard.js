frappe.pages['kennel-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Kennel Dashboard',
        single_column: true
    });

    new KennelDashboard(page);
};

class KennelDashboard {
    constructor(page) {
        this.page = page;
        this.wrapper = $(page.body);
        this.period = 'today';
        this.charts = {};

        this.render_layout();
        this.setup_date();
        this.setup_events();
        this.load_data();
    }

    render_layout() {
        this.wrapper.html(`
            <div class="kd-dashboard">
                <!-- Top Bar -->
                <div class="kd-topbar">
                    <div class="kd-topbar-left">
                        <div class="kd-brand">
                            <div class="kd-brand-icon">
                                <i class="fa fa-paw"></i>
                            </div>
                            <div>
                                <div class="kd-brand-name">FurEver</div>
                                <div class="kd-brand-sub">Kennel Management</div>
                            </div>
                        </div>
                    </div>
                    <div class="kd-topbar-center">
                        <div class="kd-search-box">
                            <i class="fa fa-search"></i>
                            <input type="text" placeholder="Search animals, kennels, applications..." class="kd-search-input" />
                        </div>
                    </div>
                    <div class="kd-topbar-right">
                        <div class="kd-topbar-date">
                            <i class="fa fa-calendar"></i>
                            <span class="kd-today-date"></span>
                        </div>
                        <button class="kd-btn-primary kd-quick-add">
                            <i class="fa fa-plus"></i> New Admission
                        </button>
                    </div>
                </div>

                <!-- Quick Nav -->
                <div class="kd-quick-nav">
                    <a class="kd-qnav-item" href="/app/animal"><i class="fa fa-paw"></i> Animals</a>
                    <a class="kd-qnav-item" href="/app/kennel"><i class="fa fa-home"></i> Kennels</a>
                    <a class="kd-qnav-item" href="/app/animal-admission"><i class="fa fa-sign-in"></i> Admissions</a>
                    <a class="kd-qnav-item" href="/app/adoption-application"><i class="fa fa-heart"></i> Adoptions</a>
                    <a class="kd-qnav-item" href="/app/veterinary-appointment"><i class="fa fa-medkit"></i> Veterinary</a>
                    <a class="kd-qnav-item" href="/app/daily-round"><i class="fa fa-clipboard"></i> Daily Rounds</a>
                    <a class="kd-qnav-item" href="/app/volunteer"><i class="fa fa-users"></i> Volunteers</a>
                    <a class="kd-qnav-item" href="/app/donation"><i class="fa fa-gift"></i> Donations</a>
                </div>

                <!-- Welcome & Period -->
                <div class="kd-content">
                    <div class="kd-welcome">
                        <div>
                            <h1 class="kd-welcome-title">Welcome back</h1>
                            <p class="kd-welcome-sub">Here's what's happening at the shelter today</p>
                        </div>
                        <div class="kd-period-selector">
                            <button class="kd-period active" data-period="today">Today</button>
                            <button class="kd-period" data-period="week">This Week</button>
                            <button class="kd-period" data-period="month">This Month</button>
                        </div>
                    </div>

                    <!-- Stats -->
                    <div class="kd-stats-grid">
                        <div class="kd-stat-card kd-c-primary kd-clickable" data-route="/app/animal">
                            <div class="kd-stat-icon"><i class="fa fa-paw"></i></div>
                            <div class="kd-stat-info">
                                <span class="kd-stat-value" id="stat-total-animals">0</span>
                                <span class="kd-stat-label">Total Animals</span>
                            </div>
                            <div class="kd-stat-trend" id="trend-animals"><i class="fa fa-arrow-up"></i> <span>-</span></div>
                        </div>
                        <div class="kd-stat-card kd-c-success kd-clickable" data-route="/app/animal?status=Available+for+Adoption">
                            <div class="kd-stat-icon"><i class="fa fa-heart"></i></div>
                            <div class="kd-stat-info">
                                <span class="kd-stat-value" id="stat-available">0</span>
                                <span class="kd-stat-label">Available for Adoption</span>
                            </div>
                            <div class="kd-stat-badge">Ready</div>
                        </div>
                        <div class="kd-stat-card kd-c-pink kd-clickable" data-route="/app/adoption-application?status=Adoption+Completed">
                            <div class="kd-stat-icon"><i class="fa fa-handshake-o"></i></div>
                            <div class="kd-stat-info">
                                <span class="kd-stat-value" id="stat-adoptions">0</span>
                                <span class="kd-stat-label">Adoptions</span>
                            </div>
                            <div class="kd-stat-trend" id="trend-adoptions"><i class="fa fa-arrow-up"></i> <span>-</span></div>
                        </div>
                        <div class="kd-stat-card kd-c-warning kd-clickable" data-route="/app/kennel">
                            <div class="kd-stat-icon"><i class="fa fa-home"></i></div>
                            <div class="kd-stat-info">
                                <span class="kd-stat-value" id="stat-occupancy">0%</span>
                                <span class="kd-stat-label">Kennel Occupancy</span>
                            </div>
                            <div class="kd-stat-bar"><div class="kd-stat-bar-fill" id="stat-occupancy-bar"></div></div>
                        </div>
                        <div class="kd-stat-card kd-c-info kd-clickable" data-route="/app/veterinary-appointment">
                            <div class="kd-stat-icon"><i class="fa fa-stethoscope"></i></div>
                            <div class="kd-stat-info">
                                <span class="kd-stat-value" id="stat-vet-today">0</span>
                                <span class="kd-stat-label">Vet Appointments Today</span>
                            </div>
                            <div class="kd-stat-badge kd-badge-urgent" id="stat-vet-urgent" style="display:none">Urgent</div>
                        </div>
                        <div class="kd-stat-card kd-c-purple kd-clickable" data-route="/app/donation">
                            <div class="kd-stat-icon"><i class="fa fa-gift"></i></div>
                            <div class="kd-stat-info">
                                <span class="kd-stat-value" id="stat-donations">R 0</span>
                                <span class="kd-stat-label">Donations This Month</span>
                            </div>
                            <div class="kd-stat-trend" id="trend-donations"><i class="fa fa-arrow-up"></i> <span>-</span></div>
                        </div>
                    </div>

                    <!-- Charts -->
                    <div class="kd-charts-row">
                        <div class="kd-card kd-chart-wide">
                            <div class="kd-card-header">
                                <h3>Intake & Adoptions</h3>
                                <div class="kd-chart-legend">
                                    <span class="kd-legend"><span class="kd-dot" style="background:#6366f1"></span> Intake</span>
                                    <span class="kd-legend"><span class="kd-dot" style="background:#10b981"></span> Adoptions</span>
                                </div>
                            </div>
                            <div class="kd-card-body"><div id="chart-intake-adoptions" class="kd-chart-area"></div></div>
                        </div>
                        <div class="kd-card">
                            <div class="kd-card-header"><h3>Animals by Species</h3></div>
                            <div class="kd-card-body"><div id="chart-species" class="kd-chart-area"></div></div>
                        </div>
                    </div>

                    <!-- Bottom Row -->
                    <div class="kd-bottom-row">
                        <div class="kd-card">
                            <div class="kd-card-header">
                                <h3>Recent Activity</h3>
                                <a class="kd-link" href="/app/animal-admission">View All</a>
                            </div>
                            <div class="kd-card-body" id="activity-list">
                                <div class="kd-loading">Loading...</div>
                            </div>
                        </div>
                        <div class="kd-card">
                            <div class="kd-card-header">
                                <h3>Today's Appointments</h3>
                                <a class="kd-link" href="/app/veterinary-appointment">View All</a>
                            </div>
                            <div class="kd-card-body" id="appointment-list">
                                <div class="kd-loading">Loading...</div>
                            </div>
                        </div>
                        <div class="kd-card">
                            <div class="kd-card-header">
                                <h3>Pending Applications</h3>
                                <a class="kd-link" href="/app/adoption-application?status=Pending">View All</a>
                            </div>
                            <div class="kd-card-body" id="pending-list">
                                <div class="kd-loading">Loading...</div>
                            </div>
                        </div>
                    </div>

                    <!-- Welfare Alerts Row -->
                    <div class="kd-bottom-row kd-welfare-row">
                        <div class="kd-card">
                            <div class="kd-card-header">
                                <h3>⚠️ Long-Stay Animals</h3>
                                <a class="kd-link" href="/app/animal">View All</a>
                            </div>
                            <div class="kd-card-body" id="long-stay-list">
                                <div class="kd-loading">Loading...</div>
                            </div>
                        </div>
                        <div class="kd-card">
                            <div class="kd-card-header">
                                <h3>🏠 Kennel Capacity</h3>
                                <a class="kd-link" href="/app/kennel">View All</a>
                            </div>
                            <div class="kd-card-body" id="capacity-overview">
                                <div class="kd-loading">Loading...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `);
    }

    setup_date() {
        var today = frappe.datetime.str_to_user(frappe.datetime.get_today());
        this.wrapper.find('.kd-today-date').text(today);
    }

    setup_events() {
        var me = this;

        this.wrapper.find('.kd-period').on('click', function() {
            me.wrapper.find('.kd-period').removeClass('active');
            $(this).addClass('active');
            me.period = $(this).data('period');
            me.load_data();
        });

        this.wrapper.find('.kd-quick-add').on('click', function() {
            frappe.new_doc('Animal Admission');
        });

        this.wrapper.find('.kd-search-input').on('keypress', function(e) {
            if (e.which === 13) {
                var query = $(this).val().trim();
                if (query) {
                    frappe.set_route('List', 'Animal', {animal_name: ['like', '%' + query + '%']});
                }
            }
        });

        // Clickable stat cards
        this.wrapper.find('.kd-clickable').on('click', function() {
            var route = $(this).data('route');
            if (route) {
                window.location.href = route;
            }
        });
    }

    load_data() {
        var me = this;
        frappe.call({
            method: 'kennel_management.api.get_dashboard_data',
            args: { period: this.period },
            callback: function(r) {
                if (r.message) {
                    me.render_stats(r.message);
                    me.render_charts(r.message);
                    me.render_activity(r.message.recent_activity || []);
                    me.render_appointments(r.message.todays_appointments || []);
                    me.render_pending(r.message.pending_applications || []);
                }
            }
        });
        // Load welfare data
        frappe.call({
            method: 'kennel_management.api.get_long_stay_animals',
            args: { threshold_days: 30 },
            callback: function(r) { me.render_long_stay(r.message || []); }
        });
        frappe.call({
            method: 'kennel_management.api.get_kennel_capacity_overview',
            callback: function(r) { if (r.message) me.render_capacity(r.message); }
        });
    }

    render_stats(data) {
        var stats = data.stats || {};

        this.wrapper.find('#stat-total-animals').text(stats.total_animals || 0);
        this.wrapper.find('#stat-available').text(stats.available || 0);
        this.wrapper.find('#stat-adoptions').text(stats.adoptions || 0);

        var occ = stats.occupancy_rate || 0;
        this.wrapper.find('#stat-occupancy').text(occ + '%');
        this.wrapper.find('#stat-occupancy-bar').css('width', occ + '%');
        if (occ > 85) this.wrapper.find('#stat-occupancy-bar').addClass('critical');
        else if (occ > 70) this.wrapper.find('#stat-occupancy-bar').addClass('warning');

        this.wrapper.find('#stat-vet-today').text(stats.vet_today || 0);
        if (stats.vet_urgent) {
            this.wrapper.find('#stat-vet-urgent').show().text(stats.vet_urgent + ' Urgent');
        }

        var don = stats.donations_amount || 0;
        this.wrapper.find('#stat-donations').text('R ' + don.toLocaleString());

        this.set_trend('#trend-animals', stats.animals_trend);
        this.set_trend('#trend-adoptions', stats.adoptions_trend);
        this.set_trend('#trend-donations', stats.donations_trend);
    }

    set_trend(selector, value) {
        var el = this.wrapper.find(selector);
        if (value === null || value === undefined) {
            el.hide();
            return;
        }
        el.show();
        if (value >= 0) {
            el.removeClass('down').addClass('up');
            el.html('<i class="fa fa-arrow-up"></i> <span>+' + value + '</span>');
        } else {
            el.removeClass('up').addClass('down');
            el.html('<i class="fa fa-arrow-down"></i> <span>' + value + '</span>');
        }
    }

    render_charts(data) {
        this.render_intake_chart(data.intake_data || [], data.adoption_data || []);
        this.render_species_chart(data.species_data || []);
    }

    render_intake_chart(intake, adoptions) {
        var container = this.wrapper.find('#chart-intake-adoptions');
        container.empty();
        if (!intake.length) {
            container.html('<div class="kd-empty">No data for this period</div>');
            return;
        }
        new frappe.Chart(container[0], {
            data: {
                labels: intake.map(function(d) { return d.label; }),
                datasets: [
                    { name: 'Intake', values: intake.map(function(d) { return d.value; }), chartType: 'bar' },
                    { name: 'Adoptions', values: adoptions.map(function(d) { return d.value; }), chartType: 'bar' }
                ]
            },
            type: 'axis-mixed',
            height: 250,
            colors: ['#6366f1', '#10b981'],
            barOptions: { spaceRatio: 0.5 },
            axisOptions: { xIsSeries: true, shortenYAxisNumbers: true }
        });
    }

    render_species_chart(species) {
        var container = this.wrapper.find('#chart-species');
        container.empty();
        if (!species.length) {
            container.html('<div class="kd-empty">No data available</div>');
            return;
        }
        new frappe.Chart(container[0], {
            data: {
                labels: species.map(function(d) { return d.label; }),
                datasets: [{ values: species.map(function(d) { return d.value; }) }]
            },
            type: 'donut',
            height: 250,
            colors: ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899']
        });
    }

    render_activity(activities) {
        var container = this.wrapper.find('#activity-list');
        if (!activities.length) {
            container.html('<div class="kd-empty"><i class="fa fa-inbox"></i><p>No recent activity</p></div>');
            return;
        }
        var icons = { admission: 'sign-in', adoption: 'heart', veterinary: 'medkit', donation: 'gift', transfer: 'exchange' };
        var html = '';
        activities.forEach(function(item) {
            var icon = icons[item.type] || 'circle';
            var time = frappe.datetime.prettyDate(item.date);
            html += '<div class="kd-activity-item">'
                + '<div class="kd-act-icon kd-act-' + item.type + '"><i class="fa fa-' + icon + '"></i></div>'
                + '<div class="kd-act-content">'
                + '<div class="kd-act-text">' + frappe.utils.escape_html(item.description) + '</div>'
                + '<div class="kd-act-time">' + time + '</div>'
                + '</div></div>';
        });
        container.html(html);
    }

    render_appointments(appointments) {
        var container = this.wrapper.find('#appointment-list');
        if (!appointments.length) {
            container.html('<div class="kd-empty"><i class="fa fa-calendar-check-o"></i><p>No appointments today</p></div>');
            return;
        }
        var html = '';
        appointments.forEach(function(item) {
            var sc = (item.status || '').toLowerCase().replace(/\s/g, '-');
            html += '<div class="kd-appt-item" onclick="frappe.set_route(\'Form\',\'Veterinary Appointment\',\'' + item.name + '\')">'
                + '<div class="kd-appt-time">' + (item.time || '--:--') + '</div>'
                + '<div class="kd-appt-info">'
                + '<div class="kd-appt-animal">' + frappe.utils.escape_html(item.animal_name || item.animal || '') + '</div>'
                + '<div class="kd-appt-type">' + frappe.utils.escape_html(item.appointment_type || '') + '</div>'
                + '</div>'
                + '<span class="kd-appt-status kd-s-' + sc + '">' + frappe.utils.escape_html(item.status || '') + '</span>'
                + '</div>';
        });
        container.html(html);
    }

    render_pending(apps) {
        var container = this.wrapper.find('#pending-list');
        if (!apps.length) {
            container.html('<div class="kd-empty"><i class="fa fa-check-circle"></i><p>No pending applications</p></div>');
            return;
        }
        var html = '';
        apps.forEach(function(item) {
            var days = frappe.datetime.get_diff(frappe.datetime.get_today(), item.creation);
            var initial = (item.applicant_name || 'A').charAt(0).toUpperCase();
            html += '<div class="kd-pend-item" onclick="frappe.set_route(\'Form\',\'Adoption Application\',\'' + item.name + '\')">'
                + '<div class="kd-pend-avatar">' + initial + '</div>'
                + '<div class="kd-pend-info">'
                + '<div class="kd-pend-name">' + frappe.utils.escape_html(item.applicant_name || '') + '</div>'
                + '<div class="kd-pend-detail">Wants: ' + frappe.utils.escape_html(item.species_preference || 'Any') + '</div>'
                + '</div>'
                + '<span class="kd-pend-days">' + days + 'd ago</span>'
                + '</div>';
        });
        container.html(html);
    }

    render_long_stay(animals) {
        var container = this.wrapper.find('#long-stay-list');
        if (!animals.length) {
            container.html('<div class="kd-empty"><i class="fa fa-check-circle" style="color:#10b981"></i><p>No long-stay animals! Great turnover.</p></div>');
            return;
        }
        var html = '';
        animals.slice(0, 8).forEach(function(a) {
            var emoji = a.species === 'Dog' ? '🐕' : a.species === 'Cat' ? '🐈' : '🐾';
            var daysColor = a.days > 60 ? '#ef4444' : a.days > 45 ? '#f59e0b' : '#6b7280';
            html += '<div class="kd-activity-item" style="cursor:pointer;" onclick="frappe.set_route(\'Form\',\'Animal\',\'' + a.name + '\')">'
                + '<div class="kd-act-icon" style="background:#fef3c7;color:#92400e;font-size:16px;">' + emoji + '</div>'
                + '<div class="kd-act-content">'
                + '<div class="kd-act-text"><strong>' + frappe.utils.escape_html(a.animal_name) + '</strong> — ' + frappe.utils.escape_html(a.breed || a.species) + '</div>'
                + '<div class="kd-act-time">' + frappe.utils.escape_html(a.status) + '</div>'
                + '</div>'
                + '<span style="color:' + daysColor + ';font-weight:700;font-size:13px;white-space:nowrap;">' + a.days + ' days</span>'
                + '</div>';
        });
        if (animals.length > 8) {
            html += '<div style="text-align:center;padding:8px;"><a href="/app/animal" class="kd-link">View all ' + animals.length + ' animals →</a></div>';
        }
        container.html(html);
    }

    render_capacity(data) {
        var container = this.wrapper.find('#capacity-overview');
        var u = data.overall_utilization || 0;
        var barColor = u >= 90 ? '#ef4444' : u >= 75 ? '#f59e0b' : '#10b981';

        var html = '<div style="margin-bottom:12px;">';
        html += '<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">';
        html += '<span>Overall: <strong>' + data.total_occupancy + '/' + data.total_capacity + '</strong></span>';
        html += '<span style="font-weight:700;color:' + barColor + ';">' + u + '%</span></div>';
        html += '<div style="height:10px;background:#e5e7eb;border-radius:5px;overflow:hidden;">';
        html += '<div style="height:100%;width:' + u + '%;background:' + barColor + ';border-radius:5px;transition:width 0.5s;"></div></div></div>';

        if (data.alerts && data.alerts.length) {
            html += '<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;padding:8px;margin-bottom:10px;">';
            data.alerts.forEach(function(a) {
                html += '<div style="font-size:12px;color:#dc2626;padding:2px 0;">⚠️ ' + a + '</div>';
            });
            html += '</div>';
        }

        // Individual kennels mini-grid
        var kennels = data.kennels || [];
        html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:6px;">';
        kennels.forEach(function(k) {
            var kUtil = k.utilization || 0;
            var bg = k.status === 'Maintenance' ? '#d1d5db' : kUtil >= 100 ? '#fee2e2' : kUtil >= 80 ? '#fef3c7' : '#ecfdf5';
            var border = k.status === 'Maintenance' ? '#9ca3af' : kUtil >= 100 ? '#ef4444' : kUtil >= 80 ? '#f59e0b' : '#10b981';
            html += '<div style="background:' + bg + ';border:1px solid ' + border + ';border-radius:6px;padding:6px;text-align:center;cursor:pointer;font-size:11px;" '
                + 'onclick="frappe.set_route(\'Form\',\'Kennel\',\'' + k.name + '\')">'
                + '<div style="font-weight:600;color:#1f2937;">' + (k.kennel_name || k.name) + '</div>'
                + '<div style="color:#6b7280;">' + k.current_occupancy + '/' + k.capacity + '</div></div>';
        });
        html += '</div>';

        container.html(html);
    }
}
