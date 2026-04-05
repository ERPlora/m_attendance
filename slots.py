"""
Attendance module slot registrations.

Defines slots that OTHER modules can fill (e.g. dashboard widgets).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.slots import SlotRegistry

MODULE_ID = "attendance"


def register_slots(slots: SlotRegistry, module_id: str) -> None:
    """
    Register slot definitions owned by the attendance module.

    Other modules can register content INTO these slots.
    The attendance module declares the extension points.

    Called by ModuleRuntime during module load.
    """
    # Declare slots for extensibility
    # e.g. attendance dashboard widgets, record detail extra sections
