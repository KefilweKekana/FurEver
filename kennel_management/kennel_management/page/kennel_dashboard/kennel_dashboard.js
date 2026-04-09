frappe.pages['kennel-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: '',
        single_column: true
    });

    // Remove default page header
    $(page.parent).find('.page-head').hide();

    // Load the dashboard
    new KennelDashboard(page);
};

class KennelDashboard {
    constructor(page) {
        this.page = page;
        this.wrapper = $(page.body);
        this.wrapper.html(frappe.render_template('kennel_dashboard'));
        this.period = 'today';
        this.charts = {};

        this.setup_date();
        this.setup_events();
        this.load_data();
    }

    setup_date() {
        const today = frappe.datetime.str_to_user(frappe.datetime.get_today());
        this.wrapper.find('.kd-today-date').text(today);
    }

    setup_events() {
        const me = this;

        // Period selector
        this.wrapper.find('.kd-period').on('click', function() {
            me.wrapper.find('.kd-period').removeClass('active');
            $(this).addClass('active');
            me.period = $(this).data('period');
            me.load_data();
        });

        // Quick add
        this.wrapper.find('.kd-quick-add').on('click', function() {
            frappe.new_doc('Animal Admission');
        });

        // Search
        this.wrapper.find('.kd-search-input').on('keypress', function(e) {
            if (e.which === 13) {
                const query = $(this).val().trim();
                if (query) {
                    frappe.set_route('List', 'Animal', {animal_name: ['like', '%' + query + '%']});
                }
            }
        });

        // Sidebar toggle
        this.wrapper.find('.kd-menu-toggle').on('click', function() {
            me.wrapper.find('.kennel-dashboard').toggleClass('kd-sidebar-collapsed');
        });

        // Sidebar nav
        this.wrapper.find('.kd-nav-item[data-section]').on('click', function() {
            me.wrapper.find('.kd-nav-item').removeClass('active');
            $(this).addClass('active');
        });
    }

    load_data() {
        const me = this;
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
    }

    render_stats(data) {
        const stats = data.stats || {};

        // Total Animals
        this.animate_counter('#stat-total-animals', stats.total_animals || 0);
        this.set_trend('#stat-animals-trend', stats.animals_trend);

        // Available
        this.animate_counter('#stat-available', stats.available || 0);

        // Adoptions
        this.animate_counter('#stat-adoptions', stats.adoptions || 0);
        this.set_trend('#stat-adoptions-trend', stats.adoptions_trend);

        // Kennel Occupancy
        const occupancy = stats.occupancy_rate || 0;
        this.wrapper.find('#stat-occupancy').text(occupancy + '%');
        this.wrapper.find('#stat-occupancy-bar').css('width', occupancy + '%');
        if (occupancy > 85) {
            this.wrapper.find('#stat-occupancy-bar').addClass('critical');
        } else if (occupancy > 70) {
            this.wrapper.find('#stat-occupancy-bar').addClass('warning');
        }

        // Vet Appointments
        this.animate_counter('#stat-vet-today', stats.vet_today || 0);
        if (stats.vet_urgent) {
            this.wrapper.find('#stat-vet-urgent').show().text(stats.vet_urgent + ' Urgent');
        }

        // Donations
        const donations = stats.donations_amount || 0;
        this.wrapper.find('#stat-donations').text('R ' + donations.toLocaleString());
        this.set_trend('#stat-donations-trend', stats.donations_trend);
    }

    animate_counter(selector, target) {
        const el = this.wrapper.find(selector);
        const current = parseInt(el.text()) || 0;
        if (current === target) return;

        $({val: current}).animate({val: target}, {
            duration: 600,
            easing: 'swing',
            step: function(now) {
                el.text(Math.round(now));
            }
        });
    }

    set_trend(selector, value) {
        const el = this.wrapper.find(selector);
        if (!value && value !== 0) {
            el.parent().hide();
            return;
        }
        el.parent().show();
        if (value >= 0) {
            el.parent().removeClass('down').addClass('up');
            el.parent().find('i').removeClass('fa-arrow-down').addClass('fa-arrow-up');
            el.text('+' + value);
        } else {
            el.parent().removeClass('up').addClass('down');
            el.parent().find('i').removeClass('fa-arrow-up').addClass('fa-arrow-down');
            el.text(value);
        }
    }

    render_charts(data) {
        this.render_intake_chart(data.intake_data || [], data.adoption_data || []);
        this.render_species_chart(data.species_data || []);
    }

    render_intake_chart(intake, adoptions) {
        const container = this.wrapper.find('#chart-intake-adoptions');
        container.empty();

        if (!intake.length && !adoptions.length) {
            container.html('<div class="kd-no-data">No data for this period</div>');
            return;
        }

        const chart = new frappe.Chart(container[0], {
            data: {
                labels: intake.map(d => d.label),
                datasets: [
                    { name: 'Intake', values: intake.map(d => d.value), chartType: 'bar' },
                    { name: 'Adoptions', values: adoptions.map(d => d.value), chartType: 'bar' }
                ]
            },
            type: 'axis-mixed',
            height: 260,
            colors: ['#6366f1', '#10b981'],
            barOptions: { spaceRatio: 0.5 },
            axisOptions: {
                xIsSeries: true,
                shortenYAxisNumbers: true
            },
            tooltipOptions: {
                formatTooltipX: d => d,
                formatTooltipY: d => d
            }
        });
    }

    render_species_chart(species_data) {
        const container = this.wrapper.find('#chart-species');
        container.empty();

        if (!species_data.length) {
            container.html('<div class="kd-no-data">No data available</div>');
            return;
        }

        const chart = new frappe.Chart(container[0], {
            data: {
                labels: species_data.map(d => d.label),
                datasets: [{ values: species_data.map(d => d.value) }]
            },
            type: 'donut',
            height: 260,
            colors: ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899']
        });
    }

    render_activity(activities) {
        const container = this.wrapper.find('#activity-list');
        if (!activities.length) {
            container.html('<div class="kd-empty-state"><i class="fa fa-inbox"></i><p>No recent activity</p></div>');
            return;
        }

        let html = '';
        activities.forEach(item => {
            const icon = this.get_activity_icon(item.type);
            const time = frappe.datetime.prettyDate(item.date);
            html += `
                <div class="kd-activity-item">
                    <div class="kd-activity-icon ${item.type}">${icon}</div>
                    <div class="kd-activity-content">
                        <span class="kd-activity-text">${item.description}</span>
                        <span class="kd-activity-time">${time}</span>
                    </div>
                </div>
            `;
        });
        container.html(html);
    }

    render_appointments(appointments) {
        const container = this.wrapper.find('#appointment-list');
        if (!appointments.length) {
            container.html('<div class="kd-empty-state"><i class="fa fa-calendar-check-o"></i><p>No appointments today</p></div>');
            return;
        }

        let html = '';
        appointments.forEach(item => {
            const status_class = (item.status || '').toLowerCase().replace(/\s/g, '-');
            html += `
                <div class="kd-appointment-item" data-name="${item.name}">
                    <div class="kd-appt-time">${item.time || '--:--'}</div>
                    <div class="kd-appt-info">
                        <span class="kd-appt-animal">${item.animal_name || item.animal}</span>
                        <span class="kd-appt-type">${item.appointment_type}</span>
                    </div>
                    <span class="kd-appt-status ${status_class}">${item.status}</span>
                </div>
            `;
        });
        container.html(html);

        // Click to open
        container.find('.kd-appointment-item').on('click', function() {
            frappe.set_route('Form', 'Veterinary Appointment', $(this).data('name'));
        });
    }

    render_pending(applications) {
        const container = this.wrapper.find('#pending-list');
        if (!applications.length) {
            container.html('<div class="kd-empty-state"><i class="fa fa-check-circle"></i><p>No pending applications</p></div>');
            return;
        }

        let html = '';
        applications.forEach(item => {
            const days = frappe.datetime.get_diff(frappe.datetime.get_today(), item.creation);
            html += `
                <div class="kd-pending-item" data-name="${item.name}">
                    <div class="kd-pending-avatar">
                        ${(item.applicant_name || 'A').charAt(0).toUpperCase()}
                    </div>
                    <div class="kd-pending-info">
                        <span class="kd-pending-name">${item.applicant_name}</span>
                        <span class="kd-pending-detail">Wants to adopt: ${item.preferred_species || 'Any animal'}</span>
                    </div>
                    <span class="kd-pending-days">${days}d ago</span>
                </div>
            `;
        });
        container.html(html);

        container.find('.kd-pending-item').on('click', function() {
            frappe.set_route('Form', 'Adoption Application', $(this).data('name'));
        });
    }

    get_activity_icon(type) {
        const icons = {
            admission: '<i class="fa fa-sign-in"></i>',
            adoption: '<i class="fa fa-heart"></i>',
            veterinary: '<i class="fa fa-medkit"></i>',
            donation: '<i class="fa fa-gift"></i>',
            transfer: '<i class="fa fa-exchange"></i>'
        };
        return icons[type] || '<i class="fa fa-circle"></i>';
    }
}
