from frappe.utils import date_diff, today, getdate


def get_animal_age(date_of_birth):
    """Return a human-readable age string from date of birth."""
    if not date_of_birth:
        return "Unknown"
    days = date_diff(today(), date_of_birth)
    if days < 0:
        return "Unknown"
    years = days // 365
    months = (days % 365) // 30
    if years > 0:
        return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
    elif months > 0:
        return f"{months} month{'s' if months != 1 else ''}"
    else:
        return f"{days} day{'s' if days != 1 else ''}"


def get_kennel_occupancy_color(current_occupancy, capacity):
    """Return a color based on occupancy percentage."""
    if capacity <= 0:
        return "grey"
    pct = (current_occupancy / capacity) * 100
    if pct >= 100:
        return "red"
    elif pct >= 75:
        return "orange"
    elif pct >= 50:
        return "yellow"
    else:
        return "green"
