"""Testy helperów run_site (bez Dockera)."""

from pathlib import Path

import pytest

from bpp.management.commands._run_site_helpers.restore import (
    detect_dump_format,
    build_restore_command,
)


def test_detect_format_sql(tmp_path):
    p = tmp_path / "x.sql"
    p.write_text("")
    assert detect_dump_format(p) == "sql"


def test_detect_format_sql_gz(tmp_path):
    p = tmp_path / "x.sql.gz"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "sql.gz"


def test_detect_format_pgdump(tmp_path):
    p = tmp_path / "x.dump"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "pgdump"


def test_detect_format_pgdump_alt(tmp_path):
    p = tmp_path / "x.pgdump"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "pgdump"


def test_detect_format_uppercase_extension(tmp_path):
    p = tmp_path / "X.SQL.GZ"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "sql.gz"


def test_detect_format_unknown(tmp_path):
    p = tmp_path / "x.tar"
    p.write_bytes(b"")
    assert detect_dump_format(p) is None


def test_build_restore_command_sql():
    cmd, decompress = build_restore_command(
        format="sql", container_id="abc123", db_user="bpp", db_name="bpp"
    )
    assert decompress is False
    assert cmd[:4] == ["docker", "exec", "-i", "abc123"]
    assert "psql" in cmd
    assert "-U" in cmd and "bpp" in cmd
    assert "-d" in cmd


def test_build_restore_command_sql_gz_decompresses():
    cmd, decompress = build_restore_command(
        format="sql.gz", container_id="abc123", db_user="bpp", db_name="bpp"
    )
    assert decompress is True  # caller pipes through gunzip
    assert "psql" in cmd


def test_build_restore_command_pgdump_uses_pg_restore():
    cmd, decompress = build_restore_command(
        format="pgdump", container_id="abc123", db_user="bpp", db_name="bpp"
    )
    assert decompress is False
    assert "pg_restore" in cmd
    assert "--clean" in cmd
    assert "--if-exists" in cmd


def test_build_restore_command_unknown_raises():
    with pytest.raises(ValueError):
        build_restore_command(
            format="tar", container_id="x", db_user="bpp", db_name="bpp"
        )
