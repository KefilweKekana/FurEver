// Redirect Kennel Management workspace to Kennel Dashboard
$(document).on('page-change', function() {
    var route = frappe.get_route();
    if (route && route[0] === 'Workspaces' && route[1] === 'Kennel Management') {
        frappe.set_route('kennel-dashboard');
    }
});
