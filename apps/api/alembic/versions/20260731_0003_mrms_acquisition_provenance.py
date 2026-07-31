"""Add MRMS acquisition provenance without replacing existing radar rows.

Revision ID: 20260731_0003
Revises: 20260731_0002
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0003"
down_revision: str | None = "20260731_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    if is_postgresql:
        _drop_append_only_trigger()

    op.add_column(
        "radar_artifacts",
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "radar_artifacts",
        sa.Column("source_bucket", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "radar_artifacts",
        sa.Column("source_etag", sa.Text(), nullable=True),
    )
    op.add_column(
        "radar_artifacts",
        sa.Column("source_last_modified", sa.DateTime(timezone=True), nullable=True),
    )

    radar_artifacts = sa.table(
        "radar_artifacts",
        sa.column("downloaded_at", sa.DateTime(timezone=True)),
        sa.column("discovered_at", sa.DateTime(timezone=True)),
        sa.column("source_bucket", sa.String(length=120)),
    )
    op.execute(
        radar_artifacts.update()
        .where(radar_artifacts.c.discovered_at.is_(None))
        .values(discovered_at=radar_artifacts.c.downloaded_at)
    )
    op.execute(
        radar_artifacts.update()
        .where(radar_artifacts.c.source_bucket.is_(None))
        .values(source_bucket="noaa-mrms-pds")
    )

    with op.batch_alter_table("radar_artifacts") as batch_op:
        batch_op.alter_column(
            "discovered_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "source_bucket",
            existing_type=sa.String(length=120),
            nullable=False,
        )

    if is_postgresql:
        _create_append_only_trigger()


def downgrade() -> None:
    with op.batch_alter_table("radar_artifacts") as batch_op:
        batch_op.drop_column("source_last_modified")
        batch_op.drop_column("source_etag")
        batch_op.drop_column("source_bucket")
        batch_op.drop_column("discovered_at")


def _drop_append_only_trigger() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_radar_artifacts_append_only ON radar_artifacts")


def _create_append_only_trigger() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_radar_artifacts_append_only
        BEFORE UPDATE OR DELETE ON radar_artifacts
        FOR EACH ROW EXECUTE FUNCTION reject_weather_archive_mutation()
        """
    )
