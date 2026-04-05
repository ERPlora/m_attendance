"""
Attendance module event subscriptions.

Registers handlers on the AsyncEventBus during module load.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.events.bus import AsyncEventBus

logger = logging.getLogger(__name__)

MODULE_ID = "attendance"


async def register_events(bus: AsyncEventBus, module_id: str) -> None:
    """
    Register event handlers for the attendance module.

    Called by ModuleRuntime during module load.
    """

    # Listen for staff member deactivation (optional integration)
    await bus.subscribe(
        "staff.member_deactivated",
        _on_staff_deactivated,
        module_id=module_id,
    )


async def _on_staff_deactivated(
    event: str,
    sender: object = None,
    employee_id: object = None,
    **kwargs: object,
) -> None:
    """
    When a staff member is deactivated, log for traceability.
    Could auto-clock-out any active sessions in the future.
    """
    if employee_id is None:
        return

    logger.info(
        "Staff member %s deactivated (attendance module notified)",
        employee_id,
    )
