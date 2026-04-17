"""Load and validate ``settings.PG_BASELINE`` into a typed config.

Projects using this package only need to set ``BASELINE_DIR`` — all
other knobs have sensible defaults and can be overridden selectively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

DEFAULT_SQL_FILENAME = "baseline.sql"
DEFAULT_META_FILENAME = "baseline.meta.json"
DEFAULT_DATABASE_ALIAS = "default"
DEFAULT_AUTO_LOAD_ON_TEST_DB = True
DEFAULT_FRESHNESS_MAX_DELTA = 50
DEFAULT_REBUILD_IMAGE = "postgres:16"

DEFAULT_PG_DUMP_EXTRA_ARGS: list[str] = [
    "--no-owner",
    "--no-acl",
    "--no-privileges",
    "--no-comments",
    "--exclude-table-data=django_session",
]

DEFAULT_FREEZE_TIMESTAMPS: list[tuple[str, list[str]]] = [
    ("django_migrations", ["applied"]),
]

DEFAULT_FREEZE_TIMESTAMP_VALUE = "2000-01-01 00:00:00+00"


@dataclass
class BaselineConfig:
    baseline_dir: Path
    sql_filename: str = DEFAULT_SQL_FILENAME
    meta_filename: str = DEFAULT_META_FILENAME
    database_alias: str = DEFAULT_DATABASE_ALIAS
    auto_load_on_test_db: bool = DEFAULT_AUTO_LOAD_ON_TEST_DB
    freshness_max_delta: int = DEFAULT_FRESHNESS_MAX_DELTA
    rebuild_image: str = DEFAULT_REBUILD_IMAGE
    pg_dump_extra_args: list[str] = field(
        default_factory=lambda: list(DEFAULT_PG_DUMP_EXTRA_ARGS)
    )
    freeze_timestamps: list[tuple[str, list[str]]] = field(
        default_factory=lambda: [
            (t, list(cols)) for (t, cols) in DEFAULT_FREEZE_TIMESTAMPS
        ]
    )
    freeze_timestamp_value: str = DEFAULT_FREEZE_TIMESTAMP_VALUE

    @property
    def sql_path(self) -> Path:
        return self.baseline_dir / self.sql_filename

    @property
    def meta_path(self) -> Path:
        return self.baseline_dir / self.meta_filename


def get_config() -> BaselineConfig:
    """Assemble a BaselineConfig from ``settings.PG_BASELINE``.

    Only ``BASELINE_DIR`` is required. Every other key is optional and
    overrides the corresponding default. Two convenience keys stack on
    top of defaults instead of replacing them:

    - ``PG_DUMP_EXTRA_EXCLUDE_TABLE_DATA``: list of patterns appended
      to ``pg_dump_extra_args`` as ``--exclude-table-data=<pattern>``.
    - ``FREEZE_TIMESTAMPS_EXTRA``: list of ``(table, [cols])`` tuples
      appended to ``freeze_timestamps``.
    """
    raw = getattr(settings, "PG_BASELINE", None) or {}
    baseline_dir = raw.get("BASELINE_DIR")
    if baseline_dir is None:
        raise RuntimeError(
            "settings.PG_BASELINE must define BASELINE_DIR (the directory "
            "holding baseline.sql + baseline.meta.json)."
        )

    pg_dump_extra_args = list(raw.get("PG_DUMP_EXTRA_ARGS", DEFAULT_PG_DUMP_EXTRA_ARGS))
    for pattern in raw.get("PG_DUMP_EXTRA_EXCLUDE_TABLE_DATA", []):
        pg_dump_extra_args.append(f"--exclude-table-data={pattern}")

    freeze_timestamps = [
        (t, list(cols))
        for (t, cols) in raw.get("FREEZE_TIMESTAMPS", DEFAULT_FREEZE_TIMESTAMPS)
    ]
    for table, cols in raw.get("FREEZE_TIMESTAMPS_EXTRA", []):
        freeze_timestamps.append((table, list(cols)))

    return BaselineConfig(
        baseline_dir=Path(baseline_dir),
        sql_filename=raw.get("SQL_FILENAME", DEFAULT_SQL_FILENAME),
        meta_filename=raw.get("META_FILENAME", DEFAULT_META_FILENAME),
        database_alias=raw.get("DATABASE_ALIAS", DEFAULT_DATABASE_ALIAS),
        auto_load_on_test_db=bool(
            raw.get("AUTO_LOAD_ON_TEST_DB", DEFAULT_AUTO_LOAD_ON_TEST_DB)
        ),
        freshness_max_delta=int(
            raw.get("FRESHNESS_MAX_DELTA", DEFAULT_FRESHNESS_MAX_DELTA)
        ),
        rebuild_image=raw.get("REBUILD_IMAGE", DEFAULT_REBUILD_IMAGE),
        pg_dump_extra_args=pg_dump_extra_args,
        freeze_timestamps=freeze_timestamps,
        freeze_timestamp_value=raw.get(
            "FREEZE_TIMESTAMP_VALUE", DEFAULT_FREEZE_TIMESTAMP_VALUE
        ),
    )
