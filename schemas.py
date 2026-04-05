"""
Pydantic schemas for attendance module.

Replaces Django forms -- used for request validation and form rendering.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ============================================================================
# Attendance Settings
# ============================================================================

class AttendanceSettingsUpdate(BaseModel):
    require_photo: bool | None = None
    allow_manual_entry: bool | None = None
    late_threshold_minutes: int | None = Field(default=None, ge=1, le=120)
    early_departure_minutes: int | None = Field(default=None, ge=1, le=120)
    auto_clock_out_hours: int | None = Field(default=None, ge=1, le=24)


# ============================================================================
# Attendance Record
# ============================================================================

class AttendanceRecordCreate(BaseModel):
    employee_id: uuid.UUID
    employee_name: str = Field(min_length=1, max_length=255)
    clock_in: datetime
    clock_out: datetime | None = None
    break_minutes: int = Field(default=0, ge=0)
    total_hours: Decimal = Field(default=Decimal("0.00"), ge=0)
    status: str = Field(default="present", max_length=20)
    notes: str = ""
    location: str | None = None
    device: str | None = None


class AttendanceRecordUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    employee_name: str | None = Field(default=None, max_length=255)
    clock_in: datetime | None = None
    clock_out: datetime | None = None
    break_minutes: int | None = Field(default=None, ge=0)
    total_hours: Decimal | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    location: str | None = None
    device: str | None = None


# ============================================================================
# Attendance Record Response (for API)
# ============================================================================

class AttendanceRecordResponse(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    clock_in: datetime
    clock_out: datetime | None
    break_minutes: int
    total_hours: Decimal
    status: str
    notes: str
    location: str | None
    device: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttendanceRecordListResponse(BaseModel):
    records: list[AttendanceRecordResponse]
    total: int


# ============================================================================
# Filters
# ============================================================================

class AttendanceFilter(BaseModel):
    search: str = ""
    status: str = ""
    date_from: str = ""
    date_to: str = ""
    employee_id: uuid.UUID | None = None
    order_by: str = "-clock_in"
    page: int = 1
    per_page: int = 25


# ============================================================================
# Bulk Action
# ============================================================================

class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1)
