"""
Attendance module HTMX views -- FastAPI router.

Replaces Django views.py + urls.py. Uses @htmx_view decorator.
Mounted at /m/attendance/ by ModuleRuntime.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, UTC
from decimal import Decimal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, or_

from app.core.db.query import HubQuery
from app.core.db.transactions import atomic
from app.core.dependencies import CurrentUser, DbSession, HubId
from app.core.htmx import htmx_view

from .models import (
    AttendanceRecord,
    AttendanceSettings,
    ATTENDANCE_STATUSES,
)
from .schemas import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceSettingsUpdate,
    BulkDeleteRequest,
)

router = APIRouter()


def _q(model, db, hub_id):
    return HubQuery(model, db, hub_id)


# ============================================================================
# Dashboard
# ============================================================================

@router.get("/")
@htmx_view(module_id="attendance", view_id="dashboard")
async def dashboard(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Attendance dashboard with today's summary."""
    today = datetime.now(UTC).date()
    week_ago = today - timedelta(days=7)

    base_q = _q(AttendanceRecord, db, hub_id)

    # Today stats
    today_q = base_q.filter(func.date(AttendanceRecord.clock_in) == today)
    present_count = await today_q.filter(
        AttendanceRecord.status.in_(["present", "remote"]),
    ).count()
    late_count = await today_q.filter(AttendanceRecord.status == "late").count()
    absent_count = await today_q.filter(AttendanceRecord.status == "absent").count()

    # Average hours today (only completed records)
    completed_today = await today_q.filter(
        AttendanceRecord.clock_out.isnot(None),
    ).all()
    avg_hours = Decimal("0.00")
    if completed_today:
        total = sum(r.total_hours for r in completed_today)
        avg_hours = (total / len(completed_today)).quantize(Decimal("0.01"))

    # Week stats
    week_q = base_q.filter(func.date(AttendanceRecord.clock_in) >= week_ago)
    records_this_week = await week_q.count()

    # Recent records
    recent_records = await (
        base_q.order_by(AttendanceRecord.clock_in.desc()).limit(10).all()
    )

    # Currently clocked in (no clock_out)
    clocked_in = await base_q.filter(
        AttendanceRecord.clock_out.is_(None),
        func.date(AttendanceRecord.clock_in) == today,
    ).all()

    return {
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "avg_hours": avg_hours,
        "records_this_week": records_this_week,
        "recent_records": recent_records,
        "clocked_in": clocked_in,
    }


# ============================================================================
# Records
# ============================================================================

@router.get("/records")
@htmx_view(module_id="attendance", view_id="records")
async def records_list(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
    search: str = "", status: str = "", date_from: str = "", date_to: str = "",
    order_by: str = "-clock_in", page: int = 1, per_page: int = 25,
):
    """Attendance records with filters, sorting, and pagination."""
    query = _q(AttendanceRecord, db, hub_id)

    if search:
        query = query.filter(or_(
            AttendanceRecord.employee_name.ilike(f"%{search}%"),
            AttendanceRecord.notes.ilike(f"%{search}%"),
        ))

    if status:
        query = query.filter(AttendanceRecord.status == status)
    if date_from:
        query = query.filter(func.date(AttendanceRecord.clock_in) >= date_from)
    if date_to:
        query = query.filter(func.date(AttendanceRecord.clock_in) <= date_to)

    # Sort
    sort_map = {
        "-clock_in": AttendanceRecord.clock_in.desc(),
        "clock_in": AttendanceRecord.clock_in,
        "-total_hours": AttendanceRecord.total_hours.desc(),
        "total_hours": AttendanceRecord.total_hours,
        "employee_name": AttendanceRecord.employee_name,
        "-employee_name": AttendanceRecord.employee_name.desc(),
        "status": AttendanceRecord.status,
        "-status": AttendanceRecord.status.desc(),
        "-created_at": AttendanceRecord.created_at.desc(),
        "created_at": AttendanceRecord.created_at,
    }
    query = query.order_by(sort_map.get(order_by, AttendanceRecord.clock_in.desc()))

    total = await query.count()
    records = await query.offset((page - 1) * per_page).limit(per_page).all()

    # Export
    export_format = request.query_params.get("export")
    if export_format in ("csv", "excel"):
        all_records = await query.all()
        if export_format == "csv":
            return _export_csv(all_records)
        return _export_excel(all_records)

    # Check if HTMX targets the table container only
    hx_target = request.headers.get("HX-Target", "")
    if hx_target == "attendance-table-container":
        return {
            "_template": "attendance/partials/records_list.html",
            "records": records,
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_next": (page * per_page) < total,
            "has_prev": page > 1,
            "search": search,
            "order_by": order_by,
            "date_from": date_from,
            "date_to": date_to,
            "status_filter": status,
        }

    return {
        "records": records,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_next": (page * per_page) < total,
        "has_prev": page > 1,
        "search": search,
        "order_by": order_by,
        "date_from": date_from,
        "date_to": date_to,
        "status_filter": status,
        "statuses": ATTENDANCE_STATUSES,
    }


# ============================================================================
# Record CRUD
# ============================================================================

@router.post("/records/add")
async def record_add(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Create an attendance record."""
    try:
        body = await request.json()
        data = AttendanceRecordCreate(**body)

        # Cross-validation: reject if employee is on approved leave.
        # find_leave_conflicts handles ImportError internally (returns None if leave not installed).
        from leave.services.conflict_detector import find_leave_conflicts
        clock_date = data.clock_in.date() if data.clock_in else datetime.now(UTC).date()
        leave_conflict = await find_leave_conflicts(db, hub_id, data.employee_id, clock_date)
        if leave_conflict:
            return JSONResponse(
                {
                    "success": False,
                    "error": (
                        f"Employee is on approved leave until {leave_conflict.end_date}. "
                        "Cannot record attendance during leave."
                    ),
                },
                status_code=409,
            )

        # F6.A — Validate employee exists in staff module (soft check, no hard FK).
        try:
            from staff.models import StaffMember
            from sqlalchemy import select as _select
            _stmt = _select(StaffMember).where(
                StaffMember.hub_id == hub_id,
                StaffMember.id == data.employee_id,
            )
            _emp = (await db.execute(_stmt)).scalar_one_or_none()
            if _emp is None:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "attendance: employee_id=%s not found in staff_member (hub=%s)",
                    data.employee_id, hub_id,
                )
                return JSONResponse(
                    {"success": False, "error": "Employee not found in Staff module."},
                    status_code=422,
                )
        except ImportError:
            pass  # staff module not installed — skip validation

        # F6.C — Schedule enforcement policy check.
        try:
            from schedules.services import is_business_hour
            from attendance.module import SCHEDULE_ENFORCEMENT_POLICY
            clock_when = data.clock_in if data.clock_in else datetime.now(UTC)
            _in_hours = await is_business_hour(db, hub_id, clock_when)
            if not _in_hours:
                import logging as _logging
                _policy = SCHEDULE_ENFORCEMENT_POLICY
                if _policy == "strict":
                    return JSONResponse(
                        {"success": False, "error": "Clock-in outside business hours."},
                        status_code=409,
                    )
                if _policy == "warning":
                    _logging.getLogger(__name__).warning(
                        "attendance: clock-in outside business hours: employee=%s hub=%s at=%s",
                        data.employee_id, hub_id, clock_when,
                    )
                # policy == "off": silent
        except (ImportError, AttributeError):
            pass  # schedules module not installed or policy not set

        async with atomic(db) as session:
            record = AttendanceRecord(
                hub_id=hub_id,
                employee_id=data.employee_id,
                employee_name=data.employee_name,
                clock_in=data.clock_in,
                clock_out=data.clock_out,
                break_minutes=data.break_minutes,
                status=data.status,
                notes=data.notes,
                location=data.location,
                device=data.device,
            )
            record.calculate_total_hours()
            session.add(record)

        return JSONResponse({"success": True, "id": str(record.id)})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@router.post("/records/{record_id}/edit")
async def record_edit(
    request: Request, record_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Edit an attendance record."""
    record = await _q(AttendanceRecord, db, hub_id).get(record_id)
    if record is None:
        return JSONResponse({"success": False, "error": "Record not found"}, status_code=404)

    try:
        body = await request.json()
        data = AttendanceRecordUpdate(**body)

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(record, key, value)

        record.calculate_total_hours()
        await db.flush()

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@router.post("/records/{record_id}/delete")
async def record_delete(
    request: Request, record_id: uuid.UUID,
    db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Soft-delete an attendance record."""
    deleted = await _q(AttendanceRecord, db, hub_id).delete(record_id)
    if not deleted:
        return JSONResponse({"success": False, "error": "Record not found"}, status_code=404)
    return JSONResponse({"success": True})


@router.post("/records/bulk")
async def records_bulk_delete(
    request: Request, db: DbSession, user: CurrentUser, hub_id: HubId,
):
    """Bulk soft-delete attendance records."""
    try:
        body = await request.json()
        data = BulkDeleteRequest(**body)

        deleted_count = 0
        for record_id in data.ids:
            ok = await _q(AttendanceRecord, db, hub_id).delete(record_id)
            if ok:
                deleted_count += 1

        return JSONResponse({"success": True, "deleted": deleted_count})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


# ============================================================================
# Settings
# ============================================================================

@router.get("/settings")
@htmx_view(module_id="attendance", view_id="settings")
async def settings_view(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Attendance settings page."""
    settings_q = _q(AttendanceSettings, db, hub_id)
    settings = await settings_q.first()
    if settings is None:
        async with atomic(db) as session:
            settings = AttendanceSettings(hub_id=hub_id)
            session.add(settings)
            await session.flush()

    return {
        "settings": settings,
    }


@router.post("/settings/save")
async def settings_save(request: Request, db: DbSession, user: CurrentUser, hub_id: HubId):
    """Save attendance settings."""
    try:
        body = await request.json()
        data = AttendanceSettingsUpdate(**body)

        settings = await _q(AttendanceSettings, db, hub_id).first()
        if settings is None:
            async with atomic(db) as session:
                settings = AttendanceSettings(hub_id=hub_id)
                session.add(settings)
                await session.flush()

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, key, value)
        await db.flush()

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


# ============================================================================
# Export helpers
# ============================================================================

def _export_csv(records: list[AttendanceRecord]) -> StreamingResponse:
    """Export attendance records as CSV."""
    output = io.StringIO()
    output.write("Employee,Clock In,Clock Out,Break (min),Total Hours,Status,Notes,Location\n")
    for r in records:
        clock_out = r.clock_out.strftime("%Y-%m-%d %H:%M") if r.clock_out else ""
        output.write(
            f'"{r.employee_name}","{r.clock_in.strftime("%Y-%m-%d %H:%M")}",'
            f'"{clock_out}",{r.break_minutes},{r.total_hours},'
            f'"{r.status}","{r.notes}","{r.location or ""}"\n'
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_records.csv"},
    )


def _export_excel(records: list[AttendanceRecord]) -> StreamingResponse:
    """Export attendance records as Excel (XLSX)."""
    try:
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Records"
        ws.append(["Employee", "Clock In", "Clock Out", "Break (min)", "Total Hours", "Status", "Notes", "Location"])

        for r in records:
            clock_out = r.clock_out.strftime("%Y-%m-%d %H:%M") if r.clock_out else ""
            ws.append([
                r.employee_name,
                r.clock_in.strftime("%Y-%m-%d %H:%M"),
                clock_out,
                r.break_minutes,
                float(r.total_hours),
                r.status,
                r.notes,
                r.location or "",
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=attendance_records.xlsx"},
        )
    except ImportError:
        return JSONResponse(
            {"success": False, "error": "Excel export requires openpyxl"},
            status_code=500,
        )
