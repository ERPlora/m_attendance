"""
Attendance module manifest.

Employee attendance tracking and clock-in/out. Tracks work hours,
breaks, late arrivals, and provides reporting on attendance patterns.
"""


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "attendance"
MODULE_NAME = "Attendance & Clock-in"
MODULE_VERSION = "2.0.2"
MODULE_ICON = "time-outline"
MODULE_DESCRIPTION = "Employee attendance tracking with clock-in/out, break management, and reporting"
MODULE_AUTHOR = "ERPlora"
MODULE_CATEGORY = "hr"

# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
HAS_MODELS = True
MIDDLEWARE = ""

# ---------------------------------------------------------------------------
# Menu (sidebar entry)
# ---------------------------------------------------------------------------
MENU = {
    "label": "Attendance",
    "icon": "time-outline",
    "order": 41,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": "Dashboard", "icon": "speedometer-outline", "view": "dashboard"},
    {"id": "records", "label": "Records", "icon": "time-outline", "view": "records"},
    {"id": "settings", "label": "Settings", "icon": "settings-outline", "view": "settings"},
]

# ---------------------------------------------------------------------------
# Dependencies (other modules required to be active)
# ---------------------------------------------------------------------------
DEPENDENCIES: list[str] = ["staff"]

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("view_attendance", "View attendance records"),
    ("add_attendance", "Add attendance records"),
    ("change_attendance", "Edit attendance records"),
    ("delete_attendance", "Delete attendance records"),
    ("manage_settings", "Manage attendance settings"),
]

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "manager": [
        "view_attendance", "add_attendance", "change_attendance",
        "delete_attendance", "manage_settings",
    ],
    "employee": ["view_attendance", "add_attendance"],
}

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
SCHEDULED_TASKS: list[dict] = []

# ---------------------------------------------------------------------------
# Pricing (free module)
# ---------------------------------------------------------------------------
# PRICING = {"monthly": 0, "yearly": 0}
