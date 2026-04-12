"""
test_schedule_enforcement.py — F6.C schedule enforcement in attendance.

Tests for is_business_hour() in schedules.services and the attendance
policy decision logic (off/warning/strict).
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from schedules.services import is_business_hour


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_business_hours(
    day_of_week: int,
    open_time: time,
    close_time: time,
    is_closed: bool = False,
    break_start: time | None = None,
    break_end: time | None = None,
) -> MagicMock:
    """Create a mock BusinessHours object."""
    bh = MagicMock()
    bh.day_of_week = day_of_week
    bh.open_time = open_time
    bh.close_time = close_time
    bh.is_closed = is_closed
    bh.break_start = break_start
    bh.break_end = break_end
    # Wire is_open_at using the real model logic
    from schedules.models import BusinessHours as BH
    real_method = BH.is_open_at
    bh.is_open_at = lambda t: real_method(bh, t)
    return bh


# ---------------------------------------------------------------------------
# Tests — is_business_hour
# ---------------------------------------------------------------------------

class TestIsBusinessHour:
    """Unit tests for schedules.services.is_business_hour."""

    @pytest.mark.asyncio
    async def test_within_business_hours_returns_true(self):
        """Clock-in at 10:00 Mon with hours 09:00-18:00 → True."""
        hub_id = uuid.uuid4()
        # Monday = 0
        when = datetime(2026, 4, 13, 10, 0, tzinfo=UTC)  # Monday 10:00

        mock_bh = _make_business_hours(0, time(9, 0), time(18, 0))
        mock_result_special = MagicMock()
        mock_result_special.scalar_one_or_none.return_value = None
        mock_result_hours = MagicMock()
        mock_result_hours.scalar_one_or_none.return_value = mock_bh

        session = AsyncMock()
        session.execute.side_effect = [mock_result_special, mock_result_hours]

        result = await is_business_hour(session, hub_id, when)
        assert result is True

    @pytest.mark.asyncio
    async def test_outside_business_hours_returns_false(self):
        """Clock-in at 20:00 Mon with hours 09:00-18:00 → False."""
        hub_id = uuid.uuid4()
        when = datetime(2026, 4, 13, 20, 0, tzinfo=UTC)  # Monday 20:00

        mock_bh = _make_business_hours(0, time(9, 0), time(18, 0))
        mock_result_special = MagicMock()
        mock_result_special.scalar_one_or_none.return_value = None
        mock_result_hours = MagicMock()
        mock_result_hours.scalar_one_or_none.return_value = mock_bh

        session = AsyncMock()
        session.execute.side_effect = [mock_result_special, mock_result_hours]

        result = await is_business_hour(session, hub_id, when)
        assert result is False

    @pytest.mark.asyncio
    async def test_special_day_closed_returns_false(self):
        """SpecialDay with is_closed=True overrides regular hours → False."""
        hub_id = uuid.uuid4()
        when = datetime(2026, 4, 13, 10, 0, tzinfo=UTC)

        mock_special = MagicMock()
        mock_special.is_closed = True
        mock_special.open_time = None
        mock_special.close_time = None

        mock_result_special = MagicMock()
        mock_result_special.scalar_one_or_none.return_value = mock_special

        session = AsyncMock()
        session.execute.return_value = mock_result_special

        result = await is_business_hour(session, hub_id, when)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_business_hours_configured_fails_open(self):
        """No BusinessHours configured for the day → fail-open → True."""
        hub_id = uuid.uuid4()
        when = datetime(2026, 4, 13, 10, 0, tzinfo=UTC)

        mock_result_special = MagicMock()
        mock_result_special.scalar_one_or_none.return_value = None
        mock_result_hours = MagicMock()
        mock_result_hours.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute.side_effect = [mock_result_special, mock_result_hours]

        result = await is_business_hour(session, hub_id, when)
        assert result is True  # fail-open when no config exists


# ---------------------------------------------------------------------------
# Tests — Policy config exists in attendance module
# ---------------------------------------------------------------------------

class TestScheduleEnforcementPolicy:
    """Ensure SCHEDULE_ENFORCEMENT_POLICY is defined and valid in attendance."""

    def test_policy_attribute_exists(self):
        from attendance.module import SCHEDULE_ENFORCEMENT_POLICY
        assert SCHEDULE_ENFORCEMENT_POLICY in ("off", "warning", "strict")

    def test_default_policy_is_warning(self):
        from attendance.module import SCHEDULE_ENFORCEMENT_POLICY
        assert SCHEDULE_ENFORCEMENT_POLICY == "warning"
