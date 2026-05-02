"""Testy helperów run_site (bez Dockera)."""

import json
from unittest.mock import patch

import pytest

from bpp.management.commands._run_site_helpers.pbn_token import (
    PbnTokenSource,
    _read_cache,
    _write_cache,
    fetch_pbn_token_via_ssh,
)
from bpp.management.commands._run_site_helpers.restore import (
    build_restore_command,
    detect_dump_format,
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
    # Brak --clean / --if-exists — zakładamy pustą bazę (caller suppressuje baseline).
    assert "--clean" not in cmd
    assert "--if-exists" not in cmd
    assert "--no-owner" in cmd
    assert "--exit-on-error" in cmd


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

# ── PBN token cache ────────────────────────────────────────────────────


def _src() -> PbnTokenSource:
    return PbnTokenSource(django_username="alice", ssh_host="prod")


def test_read_cache_returns_none_when_path_is_none():
    logs: list[str] = []
    assert _read_cache(None, _src(), logs.append) is None
    assert logs == []


def test_read_cache_returns_none_when_file_missing(tmp_path):
    logs: list[str] = []
    assert _read_cache(tmp_path / "nope", _src(), logs.append) is None
    assert logs == []


def test_read_cache_returns_payload_when_user_matches(tmp_path):
    payload = json.dumps(
        {"username": "alice", "pbn_token": "tok", "pbn_token_updated": None}
    )
    cache = tmp_path / ".saved_pbn_token"
    cache.write_text(payload)
    logs: list[str] = []
    result = _read_cache(cache, _src(), logs.append)
    assert result == payload
    assert any("wczytuję z cache" in m for m in logs)


def test_read_cache_skips_when_user_mismatches(tmp_path):
    cache = tmp_path / ".saved_pbn_token"
    cache.write_text(
        json.dumps(
            {"username": "bob", "pbn_token": "tok", "pbn_token_updated": None}
        )
    )
    logs: list[str] = []
    assert _read_cache(cache, _src(), logs.append) is None
    assert any("'bob'" in m and "'alice'" in m for m in logs)


def test_read_cache_skips_when_json_invalid(tmp_path):
    cache = tmp_path / ".saved_pbn_token"
    cache.write_text("{not json")
    logs: list[str] = []
    assert _read_cache(cache, _src(), logs.append) is None
    assert any("nieprawidłowy" in m.lower() for m in logs)


def test_write_cache_creates_file_with_chmod_600(tmp_path):
    cache = tmp_path / ".saved_pbn_token"
    payload = json.dumps({"username": "alice", "pbn_token": "tok"})
    logs: list[str] = []
    _write_cache(cache, payload, logs.append)
    assert cache.read_text() == payload
    # chmod może nie zadziałać na egzotycznych FS, ale na lokalnym tmp_path tak
    mode = cache.stat().st_mode & 0o777
    assert mode == 0o600
    assert any("zapisany do cache" in m for m in logs)


def test_write_cache_noop_when_path_is_none():
    logs: list[str] = []
    _write_cache(None, "{}", logs.append)
    assert logs == []


def test_fetch_uses_cache_and_skips_ssh(tmp_path):
    """Gdy cache ma poprawnego usera, SSH NIE jest odpalany."""
    cache = tmp_path / ".saved_pbn_token"
    cache.write_text(
        json.dumps(
            {"username": "alice", "pbn_token": "tok", "pbn_token_updated": None}
        )
    )

    logs: list[str] = []

    def fake_run(cmd, *args, **kwargs):
        # Tylko load_pbn_token powinien być wywołany — ssh nie.
        assert "ssh" not in cmd[0].lower(), f"unexpected ssh call: {cmd}"

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        return _R()

    with patch(
        "bpp.management.commands._run_site_helpers.pbn_token.subprocess.run",
        side_effect=fake_run,
    ):
        ok = fetch_pbn_token_via_ssh(
            _src(),
            remote_deploy_path="~/bpp-deploy",
            remote_compose_service="appserver",
            local_env={},
            log=logs.append,
            cache_path=cache,
        )
    assert ok is True


def test_fetch_writes_cache_after_successful_ssh(tmp_path):
    """Po pierwszym SSH cache zostaje zapisany."""
    cache = tmp_path / ".saved_pbn_token"
    assert not cache.exists()

    payload = json.dumps(
        {"username": "alice", "pbn_token": "tok", "pbn_token_updated": None}
    )

    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)

        class _R:
            returncode = 0
            stderr = ""

        if cmd[0] == "ssh":
            _R.stdout = payload + "\n"
        else:
            _R.stdout = ""
        return _R()

    logs: list[str] = []
    with patch(
        "bpp.management.commands._run_site_helpers.pbn_token.subprocess.run",
        side_effect=fake_run,
    ):
        ok = fetch_pbn_token_via_ssh(
            _src(),
            remote_deploy_path="~/bpp-deploy",
            remote_compose_service="appserver",
            local_env={},
            log=logs.append,
            cache_path=cache,
        )
    assert ok is True
    assert cache.is_file()
    assert json.loads(cache.read_text())["pbn_token"] == "tok"
    # Najpierw SSH, potem load — nie odwrotnie.
    assert calls[0][0] == "ssh"


def test_fetch_does_not_write_cache_when_ssh_fails(tmp_path):
    cache = tmp_path / ".saved_pbn_token"

    def fake_run(cmd, *args, **kwargs):
        class _R:
            returncode = 1
            stdout = ""
            stderr = "boom"

        return _R()

    logs: list[str] = []
    with patch(
        "bpp.management.commands._run_site_helpers.pbn_token.subprocess.run",
        side_effect=fake_run,
    ):
        ok = fetch_pbn_token_via_ssh(
            _src(),
            remote_deploy_path="~/bpp-deploy",
            remote_compose_service="appserver",
            local_env={},
            log=logs.append,
            cache_path=cache,
        )
    assert ok is False
    assert not cache.exists()
