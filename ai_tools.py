"""
AI tools for the Attendance module.

Uses @register_tool + AssistantTool class pattern.
All tools are async and use HubQuery for DB access.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import Any

from app.ai.registry import AssistantTool, register_tool
from app.core.db.query import HubQuery
from app.core.db.transactions import atomic

from .models import AttendanceRecord, AttendanceSettings


def _q(model, session, hub_id):
    return HubQuery(model, session, hub_id)


@register_tool
class ListAttendanceRecords(AssistantTool):
    name = "list_attendance_records"
    description = (
        "List attendance records with optional filters by employee, date range, status. "
        "Read-only -- no side effects."
    )
    module_id = "attendance"
    required_permission = "attendance.view_attendance"
    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {"type": "string", "description": "Filter by employee UUID"},
            "status": {"type": "string", "description": "Filter: present, late, absent, half_day, remote"},
            "date_from": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date filter (YYYY-MM-DD)"},
            "limit": {"type": "integer", "description": "Max results (default 20)"},
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        query = _q(AttendanceRecord, db, hub_id)

        if args.get("employee_id"):
            query = query.filter(AttendanceRecord.employee_id == uuid.UUID(args["employee_id"]))
        if args.get("status"):
            query = query.filter(AttendanceRecord.status == args["status"])
        if args.get("date_from"):
            d = datetime.strptime(args["date_from"], "%Y-%m-%d").replace(tzinfo=UTC)
            query = query.filter(AttendanceRecord.clock_in >= d)
        if args.get("date_to"):
            d = datetime.strptime(args["date_to"], "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=UTC,
            )
            query = query.filter(AttendanceRecord.clock_in <= d)

        limit = args.get("limit", 20)
        total = await query.count()
        records = await query.order_by(AttendanceRecord.clock_in.desc()).limit(limit).all()

        return {
            "records": [{
                "id": str(r.id),
                "employee_id": str(r.employee_id),
                "employee_name": r.employee_name,
                "clock_in": r.clock_in.isoformat(),
                "clock_out": r.clock_out.isoformat() if r.clock_out else None,
                "total_hours": str(r.total_hours),
                "status": r.status,
                "break_minutes": r.break_minutes,
                "notes": r.notes,
            } for r in records],
            "total": total,
        }


@register_tool
class GetAttendanceStats(AssistantTool):
    name = "get_attendance_stats"
    description = (
        "Get attendance statistics (present, late, absent counts) for a date range. "
        "Read-only."
    )
    module_id = "attendance"
    required_permission = "attendance.view_attendance"
    parameters = {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            "employee_id": {"type": "string", "description": "Filter by employee UUID"},
        },
        "required": ["date_from", "date_to"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id

        d_from = datetime.strptime(args["date_from"], "%Y-%m-%d").replace(tzinfo=UTC)
        d_to = datetime.strptime(args["date_to"], "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=UTC,
        )

        query = _q(AttendanceRecord, db, hub_id).filter(
            AttendanceRecord.clock_in >= d_from,
            AttendanceRecord.clock_in <= d_to,
        )
        if args.get("employee_id"):
            query = query.filter(AttendanceRecord.employee_id == uuid.UUID(args["employee_id"]))

        records = await query.all()

        stats = {"present": 0, "late": 0, "absent": 0, "half_day": 0, "remote": 0}
        total_hours = Decimal("0.00")
        for r in records:
            stats[r.status] = stats.get(r.status, 0) + 1
            total_hours += r.total_hours

        return {
            "period": f"{args['date_from']} to {args['date_to']}",
            "total_records": len(records),
            "total_hours": str(total_hours),
            **stats,
        }


@register_tool
class ClockIn(AssistantTool):
    name = "clock_in"
    description = (
        "Clock in an employee (create attendance record with clock_in time). "
        "Cannot clock in if already clocked in (open record exists). "
        "SIDE EFFECT. Requires confirmation."
    )
    module_id = "attendance"
    required_permission = "attendance.add_attendance"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {"type": "string", "description": "Employee UUID"},
            "employee_name": {"type": "string", "description": "Employee display name"},
            "status": {"type": "string", "description": "Status: present, late, remote (default: present)"},
            "notes": {"type": "string", "description": "Optional notes"},
        },
        "required": ["employee_id", "employee_name"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        emp_id = uuid.UUID(args["employee_id"])

        # Check for open record (clocked in but not clocked out)
        open_record = await _q(AttendanceRecord, db, hub_id).filter(
            AttendanceRecord.employee_id == emp_id,
            AttendanceRecord.clock_out == None,  # noqa: E711
        ).first()

        if open_record:
            return {
                "error": f"{args['employee_name']} is already clocked in since "
                f"{open_record.clock_in.isoformat()}. Clock out first."
            }

        now = datetime.now(UTC)
        async with atomic(db) as session:
            record = AttendanceRecord(
                hub_id=hub_id,
                employee_id=emp_id,
                employee_name=args["employee_name"],
                clock_in=now,
                status=args.get("status", "present"),
                notes=args.get("notes", ""),
            )
            session.add(record)
            await session.flush()

        return {
            "id": str(record.id),
            "employee_name": args["employee_name"],
            "clock_in": now.isoformat(),
            "clocked_in": True,
        }


@register_tool
class ClockOut(AssistantTool):
    name = "clock_out"
    description = (
        "Clock out an employee (update open record with clock_out time, calculate total_hours). "
        "Cannot clock out if not clocked in. "
        "SIDE EFFECT. Requires confirmation."
    )
    module_id = "attendance"
    required_permission = "attendance.add_attendance"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {"type": "string", "description": "Employee UUID"},
            "break_minutes": {"type": "integer", "description": "Break duration in minutes (default 0)"},
            "notes": {"type": "string", "description": "Optional notes"},
        },
        "required": ["employee_id"],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id
        emp_id = uuid.UUID(args["employee_id"])

        # Find open record
        record = await _q(AttendanceRecord, db, hub_id).filter(
            AttendanceRecord.employee_id == emp_id,
            AttendanceRecord.clock_out == None,  # noqa: E711
        ).first()

        if not record:
            return {"error": "Employee is not clocked in. No open attendance record found."}

        now = datetime.now(UTC)
        async with atomic(db):
            record.clock_out = now
            if args.get("break_minutes"):
                record.break_minutes = args["break_minutes"]
            if args.get("notes"):
                record.notes = args["notes"]
            record.calculate_total_hours()
            await db.flush()

        return {
            "id": str(record.id),
            "employee_name": record.employee_name,
            "clock_in": record.clock_in.isoformat(),
            "clock_out": now.isoformat(),
            "total_hours": str(record.total_hours),
            "clocked_out": True,
        }


@register_tool
class GetAttendanceSettings(AssistantTool):
    name = "get_attendance_settings"
    description = "Get current attendance settings. Read-only."
    module_id = "attendance"
    required_permission = "attendance.manage_settings"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id

        settings = await _q(AttendanceSettings, db, hub_id).first()
        if not settings:
            return {
                "require_photo": False,
                "allow_manual_entry": True,
                "late_threshold_minutes": 15,
                "early_departure_minutes": 15,
                "auto_clock_out_hours": 12,
            }

        return {
            "require_photo": settings.require_photo,
            "allow_manual_entry": settings.allow_manual_entry,
            "late_threshold_minutes": settings.late_threshold_minutes,
            "early_departure_minutes": settings.early_departure_minutes,
            "auto_clock_out_hours": settings.auto_clock_out_hours,
        }


@register_tool
class UpdateAttendanceSettings(AssistantTool):
    name = "update_attendance_settings"
    description = "Update attendance settings. SIDE EFFECT. Requires confirmation."
    module_id = "attendance"
    required_permission = "attendance.manage_settings"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "require_photo": {"type": "boolean", "description": "Require photo on clock-in"},
            "allow_manual_entry": {"type": "boolean", "description": "Allow manual attendance entry"},
            "late_threshold_minutes": {"type": "integer", "description": "Minutes after which an arrival is 'late'"},
            "early_departure_minutes": {"type": "integer", "description": "Minutes before end considered early departure"},
            "auto_clock_out_hours": {"type": "integer", "description": "Auto clock-out after N hours"},
        },
        "required": [],
        "additionalProperties": False,
    }

    async def execute(self, args: dict, request: Any) -> dict:
        db = request.state.db
        hub_id = request.state.hub_id

        async with atomic(db):
            settings, created = await _q(AttendanceSettings, db, hub_id).get_or_create()
            for field in (
                "require_photo", "allow_manual_entry", "late_threshold_minutes",
                "early_departure_minutes", "auto_clock_out_hours",
            ):
                if field in args:
                    setattr(settings, field, args[field])
            await db.flush()

        return {"updated": True}
