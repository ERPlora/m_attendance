"""
Attendance module AI context -- injected into the LLM system prompt.

Provides the LLM with knowledge about the module's models, relationships,
and standard operating procedures.
"""

CONTEXT = """
## Attendance Module

Employee attendance tracking and clock-in/out. Models: AttendanceSettings, AttendanceRecord.

### AttendanceRecord Model
- Fields: employee_id (UUID, indexed), employee_name (snapshot), clock_in (DateTime), clock_out (DateTime, nullable)
- Break: break_minutes (int, default 0), total_hours (Decimal 5,2, auto-calculated)
- Status: present / late / absent / half_day / remote
- Metadata: notes, location (nullable), device (nullable)

### AttendanceSettings (singleton per hub)
- require_photo: whether photo is required on clock-in (default false)
- allow_manual_entry: allow manual record creation (default true)
- late_threshold_minutes: minutes after shift start to mark as late (default 15)
- early_departure_minutes: minutes before shift end to flag early departure (default 15)
- auto_clock_out_hours: auto clock-out after N hours (default 12)

### Total Hours Calculation
- total_hours = (clock_out - clock_in - break_minutes) in hours
- Only calculated when both clock_in and clock_out are set
- Recalculated on every edit

### Key Relationships
- AttendanceRecord -> Employee (via employee_id UUID, no FK -- staff module dependency)
- AttendanceSettings is singleton per hub (UniqueConstraint on hub_id)

### Architecture Notes
- Depends on staff module for employee data
- No FK to staff tables -- uses employee_id UUID + employee_name snapshot
- Dashboard shows today's summary: present, late, absent, avg hours, currently clocked in
- Records support search, date filters, status filter, sorting, pagination
- Export to CSV and Excel
- Soft delete on records (is_deleted flag from HubBaseModel)
"""

SOPS = [
    {
        "id": "check_attendance_today",
        "triggers_es": ["asistencia de hoy", "quien esta presente", "quien ha fichado"],
        "triggers_en": ["today's attendance", "who is present", "who clocked in"],
        "steps": ["get_attendance_stats"],
        "modules_required": ["attendance"],
    },
    {
        "id": "clock_in_employee",
        "triggers_es": ["fichar entrada", "registrar entrada", "clock in"],
        "triggers_en": ["clock in", "register arrival", "start shift"],
        "steps": ["clock_in"],
        "modules_required": ["attendance"],
    },
    {
        "id": "clock_out_employee",
        "triggers_es": ["fichar salida", "registrar salida", "clock out"],
        "triggers_en": ["clock out", "register departure", "end shift"],
        "steps": ["clock_out"],
        "modules_required": ["attendance"],
    },
    {
        "id": "list_attendance",
        "triggers_es": ["ver asistencia", "registros de asistencia", "historial fichajes"],
        "triggers_en": ["view attendance", "attendance records", "attendance history"],
        "steps": ["list_attendance_records"],
        "modules_required": ["attendance"],
    },
]
