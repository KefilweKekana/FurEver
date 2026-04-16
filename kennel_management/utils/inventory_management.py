"""
Inventory & Supply Management helpers — Feature #2
Stock tracking, consumption rate calculation, and reorder alerts.
"""
import frappe
from frappe.utils import today, add_days, getdate, flt, cint, date_diff


def get_inventory_dashboard():
    """Get full inventory overview with alerts."""
    supplies = frappe.get_all("Shelter Supply",
        fields=["name", "item_name", "category", "current_stock", "unit",
                "reorder_level", "reorder_quantity", "cost_per_unit",
                "daily_consumption_rate", "estimated_days_remaining",
                "last_restocked", "supplier"],
        order_by="category asc, item_name asc")

    low_stock = []
    out_of_stock = []
    total_value = 0

    for s in supplies:
        value = flt(s.current_stock) * flt(s.cost_per_unit)
        total_value += value
        s["stock_value"] = flt(value, 2)

        if flt(s.current_stock) <= 0:
            out_of_stock.append(s)
        elif s.reorder_level and flt(s.current_stock) <= flt(s.reorder_level):
            low_stock.append(s)

    # Category breakdown
    categories = {}
    for s in supplies:
        cat = s.category or "Other"
        if cat not in categories:
            categories[cat] = {"count": 0, "value": 0, "low_stock": 0}
        categories[cat]["count"] += 1
        categories[cat]["value"] += s["stock_value"]
        if s in low_stock or s in out_of_stock:
            categories[cat]["low_stock"] += 1

    return {
        "supplies": supplies,
        "total_items": len(supplies),
        "total_value": flt(total_value, 2),
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "alert_count": len(low_stock) + len(out_of_stock),
        "categories": categories
    }


def update_consumption_rates():
    """Daily task: recalculate consumption rates based on usage history."""
    supplies = frappe.get_all("Shelter Supply",
        fields=["name", "current_stock", "last_restocked", "last_restock_quantity"])

    for s in supplies:
        if s.last_restocked and s.last_restock_quantity:
            days_since = date_diff(today(), s.last_restocked)
            if days_since > 0:
                consumed = flt(s.last_restock_quantity) - flt(s.current_stock)
                daily_rate = flt(consumed / days_since, 2)
                days_remaining = int(flt(s.current_stock) / max(daily_rate, 0.01))

                frappe.db.set_value("Shelter Supply", s.name, {
                    "daily_consumption_rate": max(daily_rate, 0),
                    "estimated_days_remaining": max(days_remaining, 0)
                })

    frappe.db.commit()


def check_reorder_alerts():
    """Daily task: check stock levels and create reorder alerts."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_inventory_management", 0):
        return

    low_items = frappe.db.sql("""
        SELECT name, item_name, category, current_stock, reorder_level,
               reorder_quantity, unit, supplier, estimated_days_remaining
        FROM `tabShelter Supply`
        WHERE current_stock <= reorder_level AND reorder_level > 0
    """, as_dict=True)

    for item in low_items:
        # Check if alert already exists
        existing = frappe.db.exists("ToDo", {
            "reference_type": "Shelter Supply",
            "reference_name": item.name,
            "status": "Open"
        })
        if existing:
            continue

        urgency = "🔴 OUT OF STOCK" if flt(item.current_stock) <= 0 else "🟡 LOW STOCK"

        managers = frappe.get_all("Has Role", filters={"role": "Kennel Manager"}, fields=["parent"])
        for m in managers:
            frappe.get_doc({
                "doctype": "ToDo",
                "description": (
                    f"{urgency}: **{item.item_name}** ({item.category})\n\n"
                    f"Current: {item.current_stock} {item.unit or 'units'}\n"
                    f"Reorder Level: {item.reorder_level}\n"
                    f"Suggested Order: {item.reorder_quantity} {item.unit or 'units'}\n"
                    f"Supplier: {item.supplier or 'Not set'}\n"
                    f"Days Remaining: ~{item.estimated_days_remaining or '?'}"
                ),
                "reference_type": "Shelter Supply",
                "reference_name": item.name,
                "allocated_to": m.parent,
                "priority": "High" if flt(item.current_stock) <= 0 else "Medium",
            }).insert(ignore_permissions=True)

    frappe.db.commit()


def record_stock_usage(supply_name, quantity_used, notes=""):
    """Record stock usage and update current stock."""
    supply = frappe.get_doc("Shelter Supply", supply_name)
    new_stock = max(0, flt(supply.current_stock) - flt(quantity_used))
    supply.current_stock = new_stock
    supply.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "item": supply.item_name,
        "used": quantity_used,
        "remaining": new_stock,
        "below_reorder": new_stock <= flt(supply.reorder_level)
    }


def record_restock(supply_name, quantity_added, cost_per_unit=None):
    """Record a restock event."""
    supply = frappe.get_doc("Shelter Supply", supply_name)
    supply.current_stock = flt(supply.current_stock) + flt(quantity_added)
    supply.last_restocked = today()
    supply.last_restock_quantity = quantity_added
    if cost_per_unit is not None:
        supply.cost_per_unit = flt(cost_per_unit)
    supply.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "item": supply.item_name,
        "added": quantity_added,
        "new_stock": supply.current_stock
    }
