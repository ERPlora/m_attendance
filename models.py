"""
Attendance module models -- SQLAlchemy 2.0.

Models: AttendanceSettings, AttendanceRecord.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import HubBaseModel

if TYPE_CHECKING:
    pass


# ============================================================================
# Attendance Settings (singleton per hub)
# ============================================================================

class AttendanceSettings(HubBaseModel):
    """Per-hub attendance configuration."""

    __tablename__ = "attendance_settings"
    __table_args__ = (
        UniqueConstraint("hub_id", name="uq_attendance_settings_hub"),
    )

    require_photo: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    allow_manual_entry: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    late_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=15, server_default="15",
    )
    early_departure_minutes: Mapped[int] = mapped_column(
        Integer, default=15, server_default="15",
    )
    auto_clock_out_hours: Mapped[int] = mapped_column(
        Integer, default=12, server_default="12",
    )

    def __repr__(self) -> str:
        return f"<AttendanceSettings hub={self.hub_id}>"


# ============================================================================
# Attendance Record
# ============================================================================

ATTENDANCE_STATUSES = ("present", "late", "absent", "half_day", "remote")

STATUS_LABELS = {
    "present": "Present",
    "late": "Late",
    "absent": "Absent",
    "half_day": "Half Day",
    "remote": "Remote",
}


class AttendanceRecord(HubBaseModel):
    """Individual attendance record for an employee."""

    __tablename__ = "attendance_record"
    __table_args__ = (
        Index("ix_attendance_hub_employee", "hub_id", "employee_id"),
        Index("ix_attendance_hub_clock_in", "hub_id", "clock_in"),
        Index("ix_attendance_hub_status", "hub_id", "status"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True,
    )
    employee_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    clock_in: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    clock_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    break_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    total_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0.00",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="present", server_default="present",
    )
    notes: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )
    location: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    device: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AttendanceRecord {self.employee_name} {self.clock_in}>"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    def calculate_total_hours(self) -> None:
        """Calculate total worked hours from clock_in, clock_out, and break_minutes."""
        if self.clock_in and self.clock_out:
            delta = self.clock_out - self.clock_in
            total_minutes = delta.total_seconds() / 60
            worked_minutes = max(total_minutes - self.break_minutes, 0)
            self.total_hours = Decimal(str(round(worked_minutes / 60, 2)))
        else:
            self.total_hours = Decimal("0.00")
