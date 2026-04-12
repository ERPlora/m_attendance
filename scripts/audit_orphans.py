"""
audit_orphans.py — Attendance module orphan employee_id audit.

Lists AttendanceRecord rows whose employee_id has no corresponding StaffMember.
Run this before adding a future hard FK constraint on employee_id.

Usage:
    python -m attendance.scripts.audit_orphans --hub-id <uuid>

Requires DATABASE_URL environment variable.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


async def audit_orphans(hub_id: uuid.UUID | None = None) -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    engine = create_async_engine(db_url)

    async with AsyncSession(engine) as session:
        # Find attendance_record rows whose employee_id is NOT in staff_member
        stmt = text("""
            SELECT
                ar.id,
                ar.hub_id,
                ar.employee_id,
                ar.employee_name,
                ar.clock_in
            FROM attendance_record ar
            WHERE NOT ar.is_deleted
              AND NOT EXISTS (
                  SELECT 1
                  FROM staff_member sm
                  WHERE sm.id = ar.employee_id
                    AND sm.hub_id = ar.hub_id
                    AND NOT sm.is_deleted
              )
            """ + ("AND ar.hub_id = :hub_id" if hub_id else "") + """
            ORDER BY ar.clock_in DESC
        """)

        params = {"hub_id": hub_id} if hub_id else {}
        result = await session.execute(stmt, params)
        rows = result.fetchall()

    await engine.dispose()

    if not rows:
        print("No orphan attendance records found.")
        return

    print(f"Found {len(rows)} orphan attendance record(s):")
    print(f"{'ID':<38} {'Hub':<38} {'employee_id':<38} {'Name':<30} {'Clock-in'}")
    print("-" * 160)
    for row in rows:
        print(f"{row.id!s:<38} {row.hub_id!s:<38} {row.employee_id!s:<38} {row.employee_name:<30} {row.clock_in}")


if __name__ == "__main__":
    _hub_id: uuid.UUID | None = None
    if "--hub-id" in sys.argv:
        idx = sys.argv.index("--hub-id")
        _hub_id = uuid.UUID(sys.argv[idx + 1])

    asyncio.run(audit_orphans(_hub_id))
