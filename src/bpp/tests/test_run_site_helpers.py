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


def test_detect_format_pg_dump_underscore(tmp_path):
    """pg_dump produkuje też pliki z extension .pg_dump (z underscore)."""
    p = tmp_path / "db-backup.pg_dump"
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


def test_banner_includes_all_endpoints():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="http://localhost:54321",
        admin_url="http://localhost:54321/admin/",
        admin_user="admin",
        admin_pass="admin",
        pg_host="127.0.0.1",
        pg_port=54322,
        redis_host="127.0.0.1",
        redis_port=54323,
        with_celery=False,
        dump_label="baseline",
    )
    assert "http://localhost:54321" in text
    assert "/admin/" in text
    assert "admin" in text
    assert "127.0.0.1:54322" in text
    assert "127.0.0.1:54323" in text
    assert "baseline" in text


def test_banner_celery_running_label():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="http://localhost:1",
        admin_url="http://localhost:1/admin/",
        admin_user="admin",
        admin_pass="admin",
        pg_host="x", pg_port=1, redis_host="x", redis_port=2,
        with_celery=True,
        dump_label="baseline",
    )
    assert "running" in text.lower()


def test_banner_celery_disabled_label():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="http://localhost:1",
        admin_url="http://localhost:1/admin/",
        admin_user="admin",
        admin_pass="admin",
        pg_host="x", pg_port=1, redis_host="x", redis_port=2,
        with_celery=False,
        dump_label="baseline",
    )
    assert "disabled" in text.lower() or "wyłączone" in text.lower()


def test_banner_dump_label_path():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="x", admin_url="y",
        admin_user="a", admin_pass="b",
        pg_host="x", pg_port=1, redis_host="y", redis_port=2,
        with_celery=False,
        dump_label="/path/to/dump.sql.gz",
    )
    assert "/path/to/dump.sql.gz" in text


def test_find_free_port_returns_int_in_range():
    from bpp.management.commands._run_site_helpers.processes import find_free_port

    port = find_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535


def test_find_free_port_unique_calls():
    """Dwa wywołania zwracają różne porty (statystycznie pewne)."""
    from bpp.management.commands._run_site_helpers.processes import find_free_port

    ports = {find_free_port() for _ in range(5)}
    assert len(ports) >= 3


def test_python_executable_is_path():
    from bpp.management.commands._run_site_helpers.processes import _python_executable

    exe = _python_executable()
    assert exe  # non-empty
    assert "python" in exe.lower()


def test_src_dir_resolves_to_src():
    from bpp.management.commands._run_site_helpers.processes import _src_dir

    p = _src_dir()
    assert p.name == "src"
    assert (p / "manage.py").exists()


def test_wait_terminate_already_exited():
    """wait_terminate na już-zakończonym procesie nie crashuje."""
    import subprocess
    from bpp.management.commands._run_site_helpers.processes import wait_terminate

    proc = subprocess.Popen(["python", "-c", "pass"])
    proc.wait()
    # Nie powinno rzucić — proc.poll() zwraca returncode
    wait_terminate(proc)
