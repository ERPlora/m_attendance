"""
Tests for attendance module models, schemas, and route registration.

Covers model fields, defaults, computed properties, schema validation,
and router path verification.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from decimal import Decimal

import pytest

from attendance.models import (
    ATTENDANCE_STATUSES,
    STATUS_LABELS,
    AttendanceRecord,
    AttendanceSettings,
)
from attendance.schemas import (
    AttendanceFilter,
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceSettingsUpdate,
    BulkDeleteRequest,
)


# ============================================================================
# Model tests — AttendanceSettings
# ============================================================================


class TestAttendanceSettings:
    """Tests for AttendanceSettings model fields and defaults."""

    async def test_repr(self, sample_settings):
        """repr should include hub identifier."""
        assert "AttendanceSettings" in repr(sample_settings)
        assert "hub=" in repr(sample_settings)

    async def test_default_values(self, sample_settings):
        """Settings should have sensible defaults."""
        assert sample_settings.require_photo is False
        assert sample_settings.allow_manual_entry is True
        assert sample_settings.late_threshold_minutes == 15
        assert sample_settings.early_departure_minutes == 15
        assert sample_settings.auto_clock_out_hours == 12

    async def test_hub_id_assigned(self, sample_settings, hub_id):
        """Settings should be scoped to the hub."""
        assert sample_settings.hub_id == hub_id

    async def test_custom_threshold(self, hub_id):
        """Custom late threshold should be stored correctly."""
        settings = AttendanceSettings(
            hub_id=hub_id,
            late_threshold_minutes=30,
            early_departure_minutes=10,
            auto_clock_out_hours=8,
        )
        assert settings.late_threshold_minutes == 30
        assert settings.early_departure_minutes == 10
        assert settings.auto_clock_out_hours == 8


# ============================================================================
# Model tests — AttendanceRecord
# ============================================================================


class TestAttendanceRecord:
    """Tests for AttendanceRecord model fields and properties."""

    async def test_repr(self, sample_record):
        """repr should include employee name and clock_in."""
        r = repr(sample_record)
        assert "Ana Lopez" in r
        assert "AttendanceRecord" in r

    async def test_fields_assigned(self, sample_record, hub_id):
        """All fields should match constructor values."""
        assert sample_record.hub_id == hub_id
        assert sample_record.employee_name == "Ana Lopez"
        assert sample_record.break_minutes == 30
        assert sample_record.total_hours == Decimal("8.00")
        assert sample_record.status == "present"
        assert sample_record.notes == "Regular shift"
        assert sample_record.location == "Main Office"
        assert sample_record.device == "Tablet-01"

    async def test_nullable_fields(self, sample_record_open):
        """clock_out, location, and device should accept None."""
        assert sample_record_open.clock_out is None
        assert sample_record_open.location is None
        assert sample_record_open.device is None

    async def test_status_label_present(self, sample_record):
        """status_label should return human-readable label for 'present'."""
        assert sample_record.status_label == "Present"

    async def test_status_label_late(self, sample_record_late):
        """status_label should return 'Late' for late records."""
        assert sample_record_late.status_label == "Late"

    async def test_status_label_all_statuses(self):
        """Every defined status should have a corresponding label."""
        for status in ATTENDANCE_STATUSES:
            assert status in STATUS_LABELS

    async def test_status_label_unknown_fallback(self, hub_id):
        """Unknown status should fall back to the raw status string."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Test",
            clock_in=datetime.now(UTC),
            status="custom_status",
        )
        assert record.status_label == "custom_status"

    async def test_status_constants(self):
        """ATTENDANCE_STATUSES should contain all expected values."""
        expected = {"present", "late", "absent", "half_day", "remote"}
        assert set(ATTENDANCE_STATUSES) == expected


# ============================================================================
# Model tests — calculate_total_hours
# ============================================================================


class TestCalculateTotalHours:
    """Tests for AttendanceRecord.calculate_total_hours()."""

    async def test_basic_calculation(self, hub_id):
        """8.5h shift minus 30min break = 8.00h."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 6, 17, 30, 0, tzinfo=UTC),
            break_minutes=30,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("8.00")

    async def test_no_break(self, hub_id):
        """8h shift with no break = 8.00h."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 6, 17, 0, 0, tzinfo=UTC),
            break_minutes=0,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("8.00")

    async def test_short_shift(self, hub_id):
        """2h shift = 2.00h."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Worker",
            clock_in=datetime(2026, 4, 6, 14, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 6, 16, 0, 0, tzinfo=UTC),
            break_minutes=0,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("2.00")

    async def test_break_exceeds_shift(self, hub_id):
        """Break longer than shift should clamp to 0.00h."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 6, 10, 0, 0, tzinfo=UTC),
            break_minutes=120,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("0.00")

    async def test_no_clock_out(self, hub_id):
        """Without clock_out, total hours should be 0.00."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            clock_out=None,
            break_minutes=0,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("0.00")

    async def test_overnight_shift(self, hub_id):
        """Overnight shift crossing midnight should calculate correctly."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Night Worker",
            clock_in=datetime(2026, 4, 6, 22, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 7, 6, 0, 0, tzinfo=UTC),
            break_minutes=0,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("8.00")

    async def test_partial_hour(self, hub_id):
        """3h15m shift should produce 3.25h."""
        record = AttendanceRecord(
            hub_id=hub_id,
            employee_id=uuid.uuid4(),
            employee_name="Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 6, 12, 15, 0, tzinfo=UTC),
            break_minutes=0,
        )
        record.calculate_total_hours()
        assert record.total_hours == Decimal("3.25")

    async def test_recalculate_updates_value(self, sample_record):
        """Calling calculate_total_hours should overwrite previous total_hours."""
        sample_record.break_minutes = 0
        sample_record.calculate_total_hours()
        # 17:30 - 09:00 = 8.5h, no break
        assert sample_record.total_hours == Decimal("8.50")


# ============================================================================
# Schema tests — AttendanceRecordCreate
# ============================================================================


class TestAttendanceRecordCreateSchema:
    """Tests for AttendanceRecordCreate Pydantic schema."""

    async def test_valid_minimal(self):
        """Minimal valid payload should work."""
        data = AttendanceRecordCreate(
            employee_id=uuid.uuid4(),
            employee_name="Test Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
        )
        assert data.employee_name == "Test Worker"
        assert data.status == "present"
        assert data.break_minutes == 0
        assert data.clock_out is None
        assert data.notes == ""

    async def test_valid_full(self):
        """Full payload with all fields should work."""
        emp_id = uuid.uuid4()
        data = AttendanceRecordCreate(
            employee_id=emp_id,
            employee_name="Full Worker",
            clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            clock_out=datetime(2026, 4, 6, 17, 0, 0, tzinfo=UTC),
            break_minutes=45,
            status="remote",
            notes="Working from home",
            location="Home",
            device="Laptop",
        )
        assert data.employee_id == emp_id
        assert data.break_minutes == 45
        assert data.status == "remote"
        assert data.location == "Home"

    async def test_empty_employee_name_rejected(self):
        """Empty employee_name should fail validation."""
        with pytest.raises(Exception):
            AttendanceRecordCreate(
                employee_id=uuid.uuid4(),
                employee_name="",
                clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            )

    async def test_missing_employee_id_rejected(self):
        """Missing employee_id should fail validation."""
        with pytest.raises(Exception):
            AttendanceRecordCreate(
                employee_name="Worker",
                clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
            )

    async def test_missing_clock_in_rejected(self):
        """Missing clock_in should fail validation."""
        with pytest.raises(Exception):
            AttendanceRecordCreate(
                employee_id=uuid.uuid4(),
                employee_name="Worker",
            )

    async def test_negative_break_minutes_rejected(self):
        """Negative break_minutes should fail validation."""
        with pytest.raises(Exception):
            AttendanceRecordCreate(
                employee_id=uuid.uuid4(),
                employee_name="Worker",
                clock_in=datetime(2026, 4, 6, 9, 0, 0, tzinfo=UTC),
                break_minutes=-10,
            )


# ============================================================================
# Schema tests — AttendanceRecordUpdate
# ============================================================================


class TestAttendanceRecordUpdateSchema:
    """Tests for AttendanceRecordUpdate Pydantic schema."""

    async def test_all_optional(self):
        """Empty update should be valid (all fields optional)."""
        data = AttendanceRecordUpdate()
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {}

    async def test_partial_update(self):
        """Partial update should only include set fields."""
        data = AttendanceRecordUpdate(status="late", notes="Arrived late")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"status": "late", "notes": "Arrived late"}
        assert "employee_id" not in dumped

    async def test_negative_break_rejected(self):
        """Negative break_minutes should fail validation."""
        with pytest.raises(Exception):
            AttendanceRecordUpdate(break_minutes=-5)


# ============================================================================
# Schema tests — AttendanceSettingsUpdate
# ============================================================================


class TestAttendanceSettingsUpdateSchema:
    """Tests for AttendanceSettingsUpdate Pydantic schema."""

    async def test_all_optional(self):
        """Empty settings update should be valid."""
        data = AttendanceSettingsUpdate()
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {}

    async def test_valid_thresholds(self):
        """Valid threshold values within range should pass."""
        data = AttendanceSettingsUpdate(
            late_threshold_minutes=30,
            early_departure_minutes=10,
            auto_clock_out_hours=8,
        )
        assert data.late_threshold_minutes == 30
        assert data.early_departure_minutes == 10
        assert data.auto_clock_out_hours == 8

    async def test_threshold_below_min_rejected(self):
        """late_threshold_minutes below 1 should fail."""
        with pytest.raises(Exception):
            AttendanceSettingsUpdate(late_threshold_minutes=0)

    async def test_threshold_above_max_rejected(self):
        """late_threshold_minutes above 120 should fail."""
        with pytest.raises(Exception):
            AttendanceSettingsUpdate(late_threshold_minutes=121)

    async def test_auto_clock_out_below_min_rejected(self):
        """auto_clock_out_hours below 1 should fail."""
        with pytest.raises(Exception):
            AttendanceSettingsUpdate(auto_clock_out_hours=0)

    async def test_auto_clock_out_above_max_rejected(self):
        """auto_clock_out_hours above 24 should fail."""
        with pytest.raises(Exception):
            AttendanceSettingsUpdate(auto_clock_out_hours=25)

    async def test_boolean_fields(self):
        """Boolean settings should accept True/False."""
        data = AttendanceSettingsUpdate(
            require_photo=True,
            allow_manual_entry=False,
        )
        assert data.require_photo is True
        assert data.allow_manual_entry is False


# ============================================================================
# Schema tests — BulkDeleteRequest
# ============================================================================


class TestBulkDeleteRequestSchema:
    """Tests for BulkDeleteRequest Pydantic schema."""

    async def test_valid_ids(self):
        """Valid list of UUIDs should pass."""
        ids = [uuid.uuid4(), uuid.uuid4()]
        data = BulkDeleteRequest(ids=ids)
        assert len(data.ids) == 2

    async def test_empty_ids_rejected(self):
        """Empty ids list should fail (min_length=1)."""
        with pytest.raises(Exception):
            BulkDeleteRequest(ids=[])

    async def test_single_id(self):
        """Single UUID in list should pass."""
        data = BulkDeleteRequest(ids=[uuid.uuid4()])
        assert len(data.ids) == 1


# ============================================================================
# Schema tests — AttendanceFilter
# ============================================================================


class TestAttendanceFilterSchema:
    """Tests for AttendanceFilter Pydantic schema."""

    async def test_defaults(self):
        """Default filter should have empty search and sensible page."""
        f = AttendanceFilter()
        assert f.search == ""
        assert f.status == ""
        assert f.date_from == ""
        assert f.date_to == ""
        assert f.employee_id is None
        assert f.order_by == "-clock_in"
        assert f.page == 1
        assert f.per_page == 25

    async def test_with_values(self):
        """Filter with explicit values should store them."""
        emp_id = uuid.uuid4()
        f = AttendanceFilter(
            search="Ana",
            status="present",
            date_from="2026-04-01",
            date_to="2026-04-06",
            employee_id=emp_id,
            order_by="employee_name",
            page=3,
            per_page=50,
        )
        assert f.search == "Ana"
        assert f.status == "present"
        assert f.employee_id == emp_id
        assert f.page == 3
        assert f.per_page == 50


# ============================================================================
# Schema tests — AttendanceRecordResponse
# ============================================================================


class TestAttendanceRecordResponseSchema:
    """Tests for AttendanceRecordResponse serialization schema."""

    async def test_from_dict(self):
        """Response schema should accept a valid dict."""
        record_id = uuid.uuid4()
        emp_id = uuid.uuid4()
        now = datetime.now(UTC)
        data = AttendanceRecordResponse(
            id=record_id,
            employee_id=emp_id,
            employee_name="Test",
            clock_in=now,
            clock_out=None,
            break_minutes=0,
            total_hours=Decimal("0.00"),
            status="present",
            notes="",
            location=None,
            device=None,
            created_at=now,
        )
        assert data.id == record_id
        assert data.clock_out is None
        assert data.total_hours == Decimal("0.00")


# ============================================================================
# Router registration tests
# ============================================================================


class TestRouterRegistration:
    """Tests that the router has all expected route paths."""

    async def test_router_exists(self):
        """Router should be importable."""
        from attendance.routes import router
        assert router is not None

    async def test_dashboard_route(self):
        """GET / (dashboard) should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/" in paths

    async def test_records_route(self):
        """GET /records should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/records" in paths

    async def test_record_add_route(self):
        """POST /records/add should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/records/add" in paths

    async def test_record_edit_route(self):
        """POST /records/{record_id}/edit should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/records/{record_id}/edit" in paths

    async def test_record_delete_route(self):
        """POST /records/{record_id}/delete should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/records/{record_id}/delete" in paths

    async def test_bulk_delete_route(self):
        """POST /records/bulk should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/records/bulk" in paths

    async def test_settings_route(self):
        """GET /settings should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/settings" in paths

    async def test_settings_save_route(self):
        """POST /settings/save should be registered."""
        from attendance.routes import router
        paths = [r.path for r in router.routes]
        assert "/settings/save" in paths


# ============================================================================
# Export helper tests
# ============================================================================


class TestExportHelpers:
    """Tests for CSV and Excel export helper functions."""

    async def test_csv_export_header(self, sample_record):
        """CSV export should include a header row."""
        from attendance.routes import _export_csv
        response = _export_csv([sample_record])
        # StreamingResponse body is an iterator; collect it
        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        body = "".join(body_parts)
        assert "Employee,Clock In,Clock Out" in body
        assert "Ana Lopez" in body

    async def test_csv_export_empty(self):
        """CSV export with no records should still have a header."""
        from attendance.routes import _export_csv
        response = _export_csv([])
        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        body = "".join(body_parts)
        assert "Employee,Clock In,Clock Out" in body
        lines = body.strip().split("\n")
        assert len(lines) == 1  # header only

    async def test_csv_export_content_type(self, sample_record):
        """CSV response should have text/csv media type."""
        from attendance.routes import _export_csv
        response = _export_csv([sample_record])
        assert response.media_type == "text/csv"

    async def test_csv_export_open_record(self, sample_record_open):
        """CSV export should handle records without clock_out."""
        from attendance.routes import _export_csv
        response = _export_csv([sample_record_open])
        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        body = "".join(body_parts)
        assert "Carlos Ruiz" in body


# ============================================================================
# Module manifest tests
# ============================================================================


class TestModuleManifest:
    """Tests for module.py manifest constants."""

    async def test_module_id(self):
        """MODULE_ID should be 'attendance'."""
        from attendance.module import MODULE_ID
        assert MODULE_ID == "attendance"

    async def test_module_has_models(self):
        """HAS_MODELS should be True."""
        from attendance.module import HAS_MODELS
        assert HAS_MODELS is True

    async def test_module_dependencies(self):
        """Module should depend on staff."""
        from attendance.module import DEPENDENCIES
        assert "staff" in DEPENDENCIES

    async def test_module_navigation(self):
        """Navigation should include dashboard, records, settings."""
        from attendance.module import NAVIGATION
        nav_ids = [n["id"] for n in NAVIGATION]
        assert "dashboard" in nav_ids
        assert "records" in nav_ids
        assert "settings" in nav_ids

    async def test_module_permissions(self):
        """PERMISSIONS should define view, add, change, delete, manage."""
        from attendance.module import PERMISSIONS
        perm_codes = [p[0] for p in PERMISSIONS]
        assert "view_attendance" in perm_codes
        assert "add_attendance" in perm_codes
        assert "change_attendance" in perm_codes
        assert "delete_attendance" in perm_codes
        assert "manage_settings" in perm_codes

    async def test_role_permissions_admin_wildcard(self):
        """Admin role should have wildcard permission."""
        from attendance.module import ROLE_PERMISSIONS
        assert "*" in ROLE_PERMISSIONS["admin"]

    async def test_role_permissions_employee_limited(self):
        """Employee role should only have view and add permissions."""
        from attendance.module import ROLE_PERMISSIONS
        emp_perms = ROLE_PERMISSIONS["employee"]
        assert "view_attendance" in emp_perms
        assert "add_attendance" in emp_perms
        assert "delete_attendance" not in emp_perms
        assert "manage_settings" not in emp_perms
