"""Initial attendance module schema.

Revision ID: 001
Revises: -
Create Date: 2026-04-05

Creates tables: attendance_settings, attendance_record.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AttendanceSettings
    op.create_table(
        "attendance_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("require_photo", sa.Boolean(), server_default="false"),
        sa.Column("allow_manual_entry", sa.Boolean(), server_default="true"),
        sa.Column("late_threshold_minutes", sa.Integer(), server_default="15"),
        sa.Column("early_departure_minutes", sa.Integer(), server_default="15"),
        sa.Column("auto_clock_out_hours", sa.Integer(), server_default="12"),
        sa.UniqueConstraint("hub_id", name="uq_attendance_settings_hub"),
    )

    # AttendanceRecord
    op.create_table(
        "attendance_record",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hub_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("employee_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("employee_name", sa.String(255), nullable=False),
        sa.Column("clock_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("break_minutes", sa.Integer(), server_default="0"),
        sa.Column("total_hours", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("status", sa.String(20), server_default="present"),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("device", sa.String(255), nullable=True),
    )
    op.create_index("ix_attendance_hub_employee", "attendance_record", ["hub_id", "employee_id"])
    op.create_index("ix_attendance_hub_clock_in", "attendance_record", ["hub_id", "clock_in"])
    op.create_index("ix_attendance_hub_status", "attendance_record", ["hub_id", "status"])


def downgrade() -> None:
    op.drop_table("attendance_record")
    op.drop_table("attendance_settings")
