"""
Test fixtures for the attendance module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from decimal import Decimal

import pytest

from attendance.models import AttendanceRecord, AttendanceSettings


@pytest.fixture
def hub_id():
    """Test hub UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_settings(hub_id):
    """Create sample attendance settings (not persisted)."""
    return AttendanceSettings(
        hub_id=hub_id,
        require_photo=False,
        allow_manual_entry=True,
        late_threshold_minutes=15,
        early_departure_minutes=15,
        auto_clock_out_hours=12,
    )


@pytest.fixture
def sample_record(hub_id):
    """Create a sample attendance record with clock_in and clock_out (not persisted)."""
    clock_in = datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC)
    clock_out = datetime(2026, 4, 6, 17, 30, 0, tzinfo=UTC)
    return AttendanceRecord(
        hub_id=hub_id,
        employee_id=uuid.uuid4(),
        employee_name="Ana Lopez",
        clock_in=clock_in,
        clock_out=clock_out,
        break_minutes=30,
        total_hours=Decimal("8.00"),
        status="present",
        notes="Regular shift",
        location="Main Office",
        device="Tablet-01",
    )


@pytest.fixture
def sample_record_open(hub_id):
    """Create a sample attendance record without clock_out (not persisted)."""
    clock_in = datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC)
    return AttendanceRecord(
        hub_id=hub_id,
        employee_id=uuid.uuid4(),
        employee_name="Carlos Ruiz",
        clock_in=clock_in,
        clock_out=None,
        break_minutes=0,
        total_hours=Decimal("0.00"),
        status="present",
        notes="",
    )


@pytest.fixture
def sample_record_late(hub_id):
    """Create a sample late attendance record (not persisted)."""
    clock_in = datetime(2026, 4, 6, 9, 45, 0, tzinfo=UTC)
    clock_out = datetime(2026, 4, 6, 18, 0, 0, tzinfo=UTC)
    return AttendanceRecord(
        hub_id=hub_id,
        employee_id=uuid.uuid4(),
        employee_name="Pedro Martinez",
        clock_in=clock_in,
        clock_out=clock_out,
        break_minutes=0,
        status="late",
        notes="Traffic delay",
    )
