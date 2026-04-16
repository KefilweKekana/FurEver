frappe.pages['kennel-heatmap'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Kennel Heatmap Dashboard',
        single_column: true
    });

    $(wrapper).find('.layout-main-section').append(frappe.render_template('kennel_heatmap'));

    var currentMetric = 'occupancy';

    function getColor(value, max) {
        var pct = (value / Math.max(max, 1)) * 100;
        if (pct >= 90) return '#F44336';
        if (pct >= 70) return '#FF9800';
        if (pct >= 40) return '#FFC107';
        return '#4CAF50';
    }

    function loadHeatmap() {
        frappe.call({
            method: 'kennel_management.api.get_kennel_heatmap_data',
            args: { metric: currentMetric },
            callback: function(r) {
                if (!r.message) return;
                var data = r.message;
                renderGrid(data.kennels || []);
                renderSummary(data.summary || {});
            }
        });
    }

    function renderGrid(kennels) {
        var grid = $('#heatmap-grid');
        grid.empty();

        kennels.forEach(function(k) {
            var color = getColor(k.value, k.max_value || 100);
            var textColor = (color === '#FFC107') ? '#333' : '#fff';

            var card = $('<div class="kennel-card" style="' +
                'background:' + color + '; color:' + textColor + '; ' +
                'padding: 15px; border-radius: 8px; cursor: pointer; ' +
                'transition: transform 0.2s; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">' +
                '<div style="font-weight: bold; font-size: 14px;">' + (k.kennel_name || k.name) + '</div>' +
                '<div style="font-size: 24px; font-weight: bold; margin: 5px 0;">' + k.display_value + '</div>' +
                '<div style="font-size: 11px; opacity: 0.9;">' + (k.subtitle || '') + '</div>' +
                '</div>');

            card.on('mouseenter', function() { $(this).css('transform', 'scale(1.05)'); });
            card.on('mouseleave', function() { $(this).css('transform', 'scale(1)'); });
            card.on('click', function() {
                frappe.set_route('Form', 'Kennel', k.name);
            });

            grid.append(card);
        });
    }

    function renderSummary(summary) {
        $('#total-kennels').html('<h4>' + (summary.total_kennels || 0) + '</h4><p>Total Kennels</p>');
        $('#total-occupied').html('<h4>' + (summary.occupied || 0) + '</h4><p>Occupied</p>');
        $('#total-available').html('<h4>' + (summary.available || 0) + '</h4><p>Available</p>');
        $('#occupancy-rate').html('<h4>' + (summary.occupancy_rate || '0%') + '</h4><p>Occupancy Rate</p>');
    }

    $('#heatmap-metric').on('change', function() {
        currentMetric = $(this).val();
        loadHeatmap();
    });

    $('#refresh-heatmap').on('click', loadHeatmap);

    loadHeatmap();
    // Auto-refresh every 60 seconds
    setInterval(loadHeatmap, 60000);
};
