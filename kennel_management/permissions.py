import frappe


def animal_permission(user):
    """Custom permission for Animal doctype."""
    if "System Manager" in frappe.get_roles(user):
        return True
    if "Kennel Manager" in frappe.get_roles(user):
        return True
    return None
