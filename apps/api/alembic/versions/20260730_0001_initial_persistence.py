"""Create public locations and immutable source provenance.

Revision ID: 20260730_0001
Revises:
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260730_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


location_kind = sa.Enum(
    "city",
    "zcta",
    name="location_kind",
    native_enum=False,
    create_constraint=True,
)
location_source_name = sa.Enum(
    "nws",
    "census",
    "config",
    name="location_source_name",
    native_enum=False,
    create_constraint=True,
)
fetch_source_name = sa.Enum(
    "nws",
    "census",
    "config",
    name="fetch_source_name",
    native_enum=False,
    create_constraint=True,
)
resource_kind = sa.Enum(
    "point",
    "forecast",
    "hourly",
    "stations",
    "observation",
    "alerts",
    "gazetteer",
    name="resource_kind",
    native_enum=False,
    create_constraint=True,
)
archive_resource_kind = sa.Enum(
    "point",
    "forecast",
    "hourly",
    "stations",
    "observation",
    "alerts",
    "gazetteer",
    name="archive_resource_kind",
    native_enum=False,
    create_constraint=True,
)
json_document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("kind", location_kind, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column(
            "country_code",
            sa.String(length=2),
            nullable=False,
        ),
        sa.Column("postal_code", sa.String(length=5), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("source_name", location_source_name, nullable=False),
        sa.Column("source_record_id", sa.String(length=64), nullable=False),
        sa.Column(
            "is_public_benchmark",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name=op.f("ck_locations_latitude_range"),
        ),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name=op.f("ck_locations_longitude_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint("slug", name=op.f("uq_locations_slug")),
        sa.UniqueConstraint(
            "source_name",
            "source_record_id",
            name="uq_locations_source_record",
        ),
    )
    op.create_index(
        "ix_locations_is_public_benchmark",
        "locations",
        ["is_public_benchmark"],
    )
    op.create_index(
        "ix_locations_normalized_name",
        "locations",
        ["normalized_name"],
    )
    op.create_index(
        "ix_locations_normalized_name_state",
        "locations",
        ["normalized_name", "state_code"],
    )
    op.create_index("ix_locations_postal_code", "locations", ["postal_code"])
    op.create_index("ix_locations_state_code", "locations", ["state_code"])

    op.create_table(
        "source_fetches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("benchmark_location_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", fetch_source_name, nullable=False),
        sa.Column("resource_kind", resource_kind, nullable=False),
        sa.Column("resource_uri", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("cache_control", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("response_headers", json_document, nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name=op.f("ck_source_fetches_duration_nonnegative"),
        ),
        sa.CheckConstraint(
            "status_code IS NULL OR (status_code >= 100 AND status_code <= 599)",
            name=op.f("ck_source_fetches_status_code_range"),
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_location_id"],
            ["locations.id"],
            name=op.f(
                "fk_source_fetches_benchmark_location_id_locations",
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_fetches")),
    )
    op.create_index(
        "ix_source_fetches_benchmark_resource_fetched",
        "source_fetches",
        ["benchmark_location_id", "resource_kind", "fetched_at"],
    )

    op.create_table(
        "benchmark_archives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_fetch_id", sa.Uuid(), nullable=False),
        sa.Column("benchmark_location_id", sa.Uuid(), nullable=False),
        sa.Column("resource_kind", archive_resource_kind, nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("payload", json_document, nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("source_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("pipeline_version", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "byte_size >= 0",
            name=op.f("ck_benchmark_archives_byte_size_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_location_id"],
            ["locations.id"],
            name=op.f(
                "fk_benchmark_archives_benchmark_location_id_locations",
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_fetch_id"],
            ["source_fetches.id"],
            name=op.f(
                "fk_benchmark_archives_source_fetch_id_source_fetches",
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark_archives")),
        sa.UniqueConstraint(
            "source_fetch_id",
            name=op.f("uq_benchmark_archives_source_fetch_id"),
        ),
    )
    op.create_index(
        "ix_benchmark_archives_content_sha256",
        "benchmark_archives",
        ["content_sha256"],
    )
    op.create_index(
        "ix_benchmark_archives_location_resource_archived",
        "benchmark_archives",
        ["benchmark_location_id", "resource_kind", "archived_at"],
    )

    op.create_table(
        "alert_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("benchmark_location_id", sa.Uuid(), nullable=False),
        sa.Column("source_fetch_id", sa.Uuid(), nullable=False),
        sa.Column("alert_identifier", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_payload", json_document, nullable=False),
        sa.Column("geometry", json_document, nullable=True),
        sa.Column("issuing_office", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("message_type", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("certainty", sa.String(length=32), nullable=True),
        sa.Column("urgency", sa.String(length=32), nullable=True),
        sa.Column("event", sa.String(length=200), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("area_description", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("onset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_location_id"],
            ["locations.id"],
            name=op.f(
                "fk_alert_revisions_benchmark_location_id_locations",
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_fetch_id"],
            ["source_fetches.id"],
            name=op.f(
                "fk_alert_revisions_source_fetch_id_source_fetches",
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_revisions")),
        sa.UniqueConstraint(
            "benchmark_location_id",
            "alert_identifier",
            "content_sha256",
            name="uq_alert_revisions_location_identifier_content",
        ),
    )
    op.create_index(
        "ix_alert_revisions_identifier_observed",
        "alert_revisions",
        ["alert_identifier", "observed_at"],
    )
    op.create_index(
        "ix_alert_revisions_location_expires",
        "alert_revisions",
        ["benchmark_location_id", "expires_at"],
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION enforce_public_benchmark_archive()
            RETURNS trigger AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM locations
                    WHERE id = NEW.benchmark_location_id
                      AND is_public_benchmark = true
                ) THEN
                    RAISE EXCEPTION
                        'archive location must be an approved public benchmark';
                END IF;
                IF TG_TABLE_NAME <> 'source_fetches' AND NOT EXISTS (
                    SELECT 1
                    FROM source_fetches
                    WHERE id::text = to_jsonb(NEW)->>'source_fetch_id'
                      AND benchmark_location_id = NEW.benchmark_location_id
                ) THEN
                    RAISE EXCEPTION
                        'archive provenance must use the same benchmark location';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """,
        )
        for table_name in (
            "source_fetches",
            "benchmark_archives",
            "alert_revisions",
        ):
            op.execute(
                f"""
                CREATE TRIGGER trg_{table_name}_public_benchmark
                BEFORE INSERT ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION enforce_public_benchmark_archive()
                """,
            )

        op.execute(
            """
            CREATE FUNCTION reject_weather_archive_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql
            """,
        )
        for table_name in (
            "source_fetches",
            "benchmark_archives",
            "alert_revisions",
        ):
            op.execute(
                f"""
                CREATE TRIGGER trg_{table_name}_append_only
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION reject_weather_archive_mutation()
                """,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in (
            "source_fetches",
            "benchmark_archives",
            "alert_revisions",
        ):
            op.execute(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_public_benchmark ON {table_name}",
            )
            op.execute(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}",
            )
        op.execute("DROP FUNCTION IF EXISTS enforce_public_benchmark_archive")
        op.execute("DROP FUNCTION IF EXISTS reject_weather_archive_mutation")

    op.drop_index(
        "ix_alert_revisions_location_expires",
        table_name="alert_revisions",
    )
    op.drop_index(
        "ix_alert_revisions_identifier_observed",
        table_name="alert_revisions",
    )
    op.drop_table("alert_revisions")
    op.drop_index(
        "ix_benchmark_archives_location_resource_archived",
        table_name="benchmark_archives",
    )
    op.drop_index(
        "ix_benchmark_archives_content_sha256",
        table_name="benchmark_archives",
    )
    op.drop_table("benchmark_archives")
    op.drop_index(
        "ix_source_fetches_benchmark_resource_fetched",
        table_name="source_fetches",
    )
    op.drop_table("source_fetches")
    op.drop_index("ix_locations_state_code", table_name="locations")
    op.drop_index("ix_locations_postal_code", table_name="locations")
    op.drop_index(
        "ix_locations_normalized_name_state",
        table_name="locations",
    )
    op.drop_index("ix_locations_normalized_name", table_name="locations")
    op.drop_index(
        "ix_locations_is_public_benchmark",
        table_name="locations",
    )
    op.drop_table("locations")
