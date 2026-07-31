"""Add immutable metadata for normalized MRMS radar artifacts.

Revision ID: 20260731_0002
Revises: 20260730_0001
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260731_0002"
down_revision: str | None = "20260730_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "radar_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=16),
            server_default=sa.text("'mrms'"),
            nullable=False,
        ),
        sa.Column("region_id", sa.String(length=120), nullable=False),
        sa.Column("product", sa.String(length=200), nullable=False),
        sa.Column("variable", sa.String(length=120), nullable=False),
        sa.Column("units", sa.String(length=32), nullable=False),
        sa.Column("source_object_key", sa.String(length=512), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("compressed_sha256", sa.String(length=64), nullable=False),
        sa.Column("grib_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=False),
        sa.Column("normalized_zarr_path", sa.Text(), nullable=False),
        sa.Column("preview_path", sa.Text(), nullable=True),
        sa.Column("observation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_projection", sa.Text(), nullable=False),
        sa.Column("target_projection", sa.Text(), nullable=False),
        sa.Column("geographic_bounds", json_document, nullable=False),
        sa.Column("horizontal_resolution_m", sa.Float(), nullable=False),
        sa.Column("width_pixels", sa.Integer(), nullable=False),
        sa.Column("height_pixels", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("missing_percentage", sa.Float(), nullable=False),
        sa.Column("no_coverage_percentage", sa.Float(), nullable=False),
        sa.Column("source_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("processing_version", sa.String(length=80), nullable=False),
        sa.Column(
            "processing_state",
            sa.String(length=24),
            server_default=sa.text("'completed'"),
            nullable=False,
        ),
        sa.Column("quality_flags", json_document, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source = 'mrms'",
            name=op.f("ck_radar_artifacts_source_mrms"),
        ),
        sa.CheckConstraint(
            "processing_state = 'completed'",
            name=op.f("ck_radar_artifacts_processing_state_completed"),
        ),
        sa.CheckConstraint(
            "length(compressed_sha256) = 64",
            name=op.f("ck_radar_artifacts_compressed_sha256_length"),
        ),
        sa.CheckConstraint(
            "length(grib_sha256) = 64",
            name=op.f("ck_radar_artifacts_grib_sha256_length"),
        ),
        sa.CheckConstraint(
            "horizontal_resolution_m > 0",
            name=op.f("ck_radar_artifacts_horizontal_resolution_positive"),
        ),
        sa.CheckConstraint(
            "width_pixels > 0",
            name=op.f("ck_radar_artifacts_width_pixels_positive"),
        ),
        sa.CheckConstraint(
            "height_pixels > 0",
            name=op.f("ck_radar_artifacts_height_pixels_positive"),
        ),
        sa.CheckConstraint(
            "min_value IS NULL OR max_value IS NULL OR min_value <= max_value",
            name=op.f("ck_radar_artifacts_value_range_ordered"),
        ),
        sa.CheckConstraint(
            "missing_percentage >= 0 AND missing_percentage <= 100",
            name=op.f("ck_radar_artifacts_missing_percentage_range"),
        ),
        sa.CheckConstraint(
            "no_coverage_percentage >= 0 AND no_coverage_percentage <= 100",
            name=op.f("ck_radar_artifacts_no_coverage_percentage_range"),
        ),
        sa.CheckConstraint(
            "missing_percentage + no_coverage_percentage <= 100",
            name=op.f("ck_radar_artifacts_masked_percentage_total_range"),
        ),
        sa.CheckConstraint(
            "source_byte_size >= 0",
            name=op.f("ck_radar_artifacts_source_byte_size_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_radar_artifacts")),
        sa.UniqueConstraint(
            "region_id",
            "source_object_key",
            "processing_version",
            name="uq_radar_artifacts_region_source_object_processing",
        ),
        sa.UniqueConstraint(
            "region_id",
            "compressed_sha256",
            "processing_version",
            name="uq_radar_artifacts_region_compressed_sha_processing",
        ),
    )
    op.create_index(
        "ix_radar_artifacts_region_product_valid_time",
        "radar_artifacts",
        ["region_id", "product", "valid_time"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE TRIGGER trg_radar_artifacts_append_only
            BEFORE UPDATE OR DELETE ON radar_artifacts
            FOR EACH ROW EXECUTE FUNCTION reject_weather_archive_mutation()
            """,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_radar_artifacts_append_only ON radar_artifacts",
        )

    op.drop_index(
        "ix_radar_artifacts_region_product_valid_time",
        table_name="radar_artifacts",
    )
    op.drop_table("radar_artifacts")
