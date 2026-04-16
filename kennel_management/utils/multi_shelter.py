"""
Multi-Shelter Network — Feature #14
Inter-shelter transfers, shared capacity, and network-wide analytics.
"""
import frappe
from frappe.utils import today, flt, cint


def get_network_overview():
    """Get overview of all shelter locations in the network."""
    locations = frappe.get_all("Shelter Location",
        fields=["name", "location_name", "location_code", "is_primary",
                "total_kennels", "total_capacity", "current_population",
                "species_handled", "manager_name", "phone"],
        order_by="is_primary desc, location_name asc")

    # Update current population for each location
    for loc in locations:
        pop = frappe.db.count("Animal", {
            "shelter_location": loc.name,
            "status": ["in", ["Available for Adoption", "Under Medical Care",
                             "In Foster Care", "Quarantine", "Under Evaluation", "Boarding"]]
        })
        if pop != loc.current_population:
            frappe.db.set_value("Shelter Location", loc.name, "current_population", pop)
            loc["current_population"] = pop

        loc["occupancy_percent"] = flt(pop / max(loc.total_capacity or 1, 1) * 100, 1)

    total_capacity = sum(cint(l.total_capacity) for l in locations)
    total_pop = sum(cint(l.current_population) for l in locations)

    return {
        "locations": locations,
        "total_locations": len(locations),
        "total_capacity": total_capacity,
        "total_population": total_pop,
        "network_occupancy": flt(total_pop / max(total_capacity, 1) * 100, 1)
    }


def initiate_transfer(animal_name, from_location, to_location, reason=""):
    """Initiate an animal transfer between shelter locations.

    Creates an Animal Transfer record and updates the animal's location.
    """
    animal = frappe.get_doc("Animal", animal_name)

    # Validate destination has capacity
    dest = frappe.get_doc("Shelter Location", to_location)
    if dest.total_capacity and dest.current_population >= dest.total_capacity:
        return {"status": "error", "message": f"{dest.location_name} is at full capacity"}

    # Create transfer record
    transfer = frappe.get_doc({
        "doctype": "Animal Transfer",
        "animal": animal_name,
        "transfer_date": today(),
        "from_location": from_location,
        "to_location": to_location,
        "reason": reason,
        "status": "Pending"
    })
    transfer.insert(ignore_permissions=True)

    frappe.db.commit()
    return {
        "status": "success",
        "transfer": transfer.name,
        "message": f"Transfer initiated for {animal.animal_name} to {dest.location_name}"
    }


def complete_transfer(transfer_name):
    """Complete an animal transfer — update animal location."""
    transfer = frappe.get_doc("Animal Transfer", transfer_name)

    if transfer.status != "Pending":
        return {"status": "error", "message": f"Transfer is already {transfer.status}"}

    # Update animal's location
    animal = frappe.get_doc("Animal", transfer.animal)
    if hasattr(animal, "shelter_location"):
        animal.shelter_location = transfer.to_location
        animal.save(ignore_permissions=True)

    transfer.status = "Completed"
    transfer.save(ignore_permissions=True)

    # Update population counts
    _refresh_location_counts(transfer.from_location)
    _refresh_location_counts(transfer.to_location)

    frappe.db.commit()
    return {"status": "success", "message": f"Transfer completed for {animal.animal_name}"}


def _refresh_location_counts(location_name):
    """Refresh the population count for a shelter location."""
    if not location_name:
        return
    pop = frappe.db.count("Animal", {
        "shelter_location": location_name,
        "status": ["in", ["Available for Adoption", "Under Medical Care",
                         "In Foster Care", "Quarantine", "Under Evaluation", "Boarding"]]
    })
    frappe.db.set_value("Shelter Location", location_name, "current_population", pop)


def get_transfer_recommendations():
    """Analyze network capacity and suggest transfers to balance load."""
    locations = frappe.get_all("Shelter Location",
        fields=["name", "location_name", "total_capacity", "current_population", "species_handled"],
        order_by="location_name asc")

    overcrowded = []
    has_space = []

    for loc in locations:
        cap = cint(loc.total_capacity) or 50
        pop = cint(loc.current_population)
        occ = flt(pop / cap * 100, 1)
        loc["occupancy"] = occ

        if occ >= 85:
            overcrowded.append(loc)
        elif occ < 60:
            has_space.append(loc)

    recommendations = []
    for over in overcrowded:
        for space in has_space:
            available = cint(space.total_capacity) - cint(space.current_population)
            excess = cint(over.current_population) - int(cint(over.total_capacity) * 0.75)
            transfer_count = min(available, excess)

            if transfer_count > 0:
                recommendations.append({
                    "from": over.location_name,
                    "from_occupancy": over["occupancy"],
                    "to": space.location_name,
                    "to_occupancy": space["occupancy"],
                    "suggested_transfers": transfer_count,
                    "reason": f"Balance load: {over.location_name} at {over['occupancy']}%, "
                              f"{space.location_name} at {space['occupancy']}%"
                })

    return {
        "recommendations": recommendations,
        "overcrowded": [l.location_name for l in overcrowded],
        "available_space": [l.location_name for l in has_space]
    }
