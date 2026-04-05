"""
Attendance module AI tools for the assistant.

Tools for querying attendance data, creating records, managing settings.
"""

from __future__ import annotations


# AI tools will be registered here following the same @register_tool pattern.
# The attendance module exposes tools for:
# - list_attendance: Query attendance records by date, status, employee
# - get_attendance_stats: Present/late/absent counts by period
# - clock_in_employee: Clock in an employee
# - clock_out_employee: Clock out an employee
# - get_attendance_settings: Read current settings
# - update_attendance_settings: Update settings

TOOLS = []
