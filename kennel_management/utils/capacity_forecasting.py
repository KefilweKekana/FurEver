"""
Smart Capacity Forecasting — Feature #3
Historical data analysis + seasonal prediction for shelter capacity planning.
"""
import frappe
from frappe.utils import today, add_days, getdate, cint, flt, date_diff, nowdate


def get_capacity_forecast(days_ahead=30):
    """Generate capacity forecast based on historical intake/outcome trends."""
    now = getdate(today())
    history_days = 180

    # Current population
    current_pop = frappe.db.count("Animal", {"status": ["in", [
        "Available for Adoption", "Under Medical Care", "In Foster Care",
        "Quarantine", "Under Evaluation", "Boarding"
    ]]})

    # Total kennel capacity
    total_capacity = frappe.db.sql("""
        SELECT COALESCE(SUM(capacity), 0) as total
        FROM `tabKennel` WHERE status = 'Active'
    """)[0][0] or 50

    # Historical daily intake rate (animals admitted per day)
    intake_count = frappe.db.count("Animal", {
        "intake_date": [">=", add_days(now, -history_days)],
        "intake_date": ["<=", nowdate()]
    }) or 0
    daily_intake = flt(intake_count / max(history_days, 1), 2)

    # Historical daily outcome rate (adoptions + transfers out per day)
    adoption_count = frappe.db.count("Adoption Application", {
        "status": "Approved",
        "modified": [">=", add_days(now, -history_days)]
    }) or 0
    daily_outcome = flt(adoption_count / max(history_days, 1), 2)

    # Net daily change
    net_daily = flt(daily_intake - daily_outcome, 2)

    # Forecast
    forecast = []
    projected = current_pop
    for day in range(1, days_ahead + 1):
        projected = max(0, projected + net_daily)
        future_date = add_days(now, day)
        occupancy_pct = flt(projected / max(total_capacity, 1) * 100, 1)

        forecast.append({
            "date": str(future_date),
            "projected_population": round(projected),
            "occupancy_percent": occupancy_pct,
            "status": "Critical" if occupancy_pct >= 95 else "Warning" if occupancy_pct >= 80 else "Normal"
        })

    # Monthly breakdown by species
    species_breakdown = frappe.db.sql("""
        SELECT species, COUNT(*) as count
        FROM `tabAnimal`
        WHERE status IN ('Available for Adoption', 'Under Medical Care',
                         'In Foster Care', 'Quarantine', 'Under Evaluation', 'Boarding')
        GROUP BY species ORDER BY count DESC
    """, as_dict=True)

    return {
        "current_population": current_pop,
        "total_capacity": cint(total_capacity),
        "occupancy_percent": flt(current_pop / max(total_capacity, 1) * 100, 1),
        "daily_intake_rate": daily_intake,
        "daily_outcome_rate": daily_outcome,
        "net_daily_change": net_daily,
        "forecast": forecast,
        "species_breakdown": species_breakdown,
        "recommendations": _get_recommendations(current_pop, total_capacity, net_daily, daily_intake)
    }


def _get_recommendations(population, capacity, net_daily, intake_rate):
    """Generate actionable recommendations based on trends."""
    recs = []
    occ_pct = flt(population / max(capacity, 1) * 100, 1)

    if occ_pct >= 90:
        recs.append({
            "priority": "Critical",
            "action": "Organize emergency adoption event — shelter at {0}% capacity".format(occ_pct)
        })
    if occ_pct >= 80:
        recs.append({
            "priority": "High",
            "action": "Increase foster recruitment efforts to free kennel space"
        })
    if net_daily > 0.5:
        recs.append({
            "priority": "High",
            "action": "Intake rate exceeding outcomes — consider intake freeze for non-emergencies"
        })
    if intake_rate > 3:
        recs.append({
            "priority": "Medium",
            "action": "High intake volume detected — review community spay/neuter programs"
        })
    if occ_pct < 50:
        recs.append({
            "priority": "Info",
            "action": "Good capacity available — consider accepting transfers from overcrowded shelters"
        })

    return recs


def run_daily_forecast():
    """Daily task: check capacity and alert if approaching critical levels."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_capacity_forecasting", 0):
        return

    forecast = get_capacity_forecast(14)

    if forecast["occupancy_percent"] >= 85:
        # Send alert
        managers = frappe.get_all("Has Role", filters={"role": "Kennel Manager"}, fields=["parent"])
        for m in managers:
            frappe.get_doc({
                "doctype": "ToDo",
                "description": (
                    f"⚠️ **Capacity Alert**: Shelter at {forecast['occupancy_percent']}% capacity "
                    f"({forecast['current_population']}/{forecast['total_capacity']}). "
                    f"Net daily change: {forecast['net_daily_change']:+.1f} animals/day."
                ),
                "allocated_to": m.parent,
                "priority": "High",
            }).insert(ignore_permissions=True)

    frappe.db.commit()
