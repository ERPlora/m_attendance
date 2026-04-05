"""
Attendance module hook registrations.

Registers actions and filters on the HookRegistry during module load.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.hooks.registry import HookRegistry

MODULE_ID = "attendance"


def register_hooks(hooks: HookRegistry, module_id: str) -> None:
    """
    Register hooks for the attendance module.

    Called by ModuleRuntime during module load.
    """
    # Action: after clock-in -- other modules can subscribe
    hooks.add_action(
        "attendance.clock_in",
        _on_clock_in_action,
        priority=10,
        module_id=module_id,
    )

    # Action: after clock-out -- other modules can subscribe
    hooks.add_action(
        "attendance.clock_out",
        _on_clock_out_action,
        priority=10,
        module_id=module_id,
    )


async def _on_clock_in_action(
    record=None,
    session=None,
    **kwargs,
) -> None:
    """
    Default action when an employee clocks in.
    Other modules can add_action('attendance.clock_in', ...) to extend.
    """


async def _on_clock_out_action(
    record=None,
    session=None,
    **kwargs,
) -> None:
    """
    Default action when an employee clocks out.
    Other modules can add_action('attendance.clock_out', ...) to extend.
    """
