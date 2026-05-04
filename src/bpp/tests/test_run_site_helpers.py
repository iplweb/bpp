"""Testy helperów run_site (bez Dockera)."""

import json
from unittest.mock import patch

import pytest

from bpp.management.commands._run_site_helpers.pbn_token import (
    PbnTokenSource,
    _quote_remote_path,
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
        format="pgdump",
        container_id="abc123",
        db_user="bpp",
        db_name="bpp",
        dump_in_container="/tmp/x.pgdump",
    )
    assert decompress is False
    assert "pg_restore" in cmd
    # Brak --clean / --if-exists — zakładamy pustą bazę (caller suppressuje baseline).
    assert "--clean" not in cmd
    assert "--if-exists" not in cmd
    assert "--no-owner" in cmd
    assert "--exit-on-error" in cmd
    # Plik musi być pozytywnym argumentem (pg_restore -j wymaga seekable file).
    assert cmd[-1] == "/tmp/x.pgdump"


def test_build_restore_command_pgdump_jobs_1_omits_dash_j():
    cmd, _ = build_restore_command(
        format="pgdump",
        container_id="abc",
        dump_in_container="/tmp/x.pgdump",
        jobs=1,
    )
    assert "-j" not in cmd


def test_build_restore_command_pgdump_jobs_gt_1_adds_parallel_flag():
    cmd, _ = build_restore_command(
        format="pgdump",
        container_id="abc",
        dump_in_container="/tmp/x.pgdump",
        jobs=8,
    )
    assert "-j" in cmd
    j_idx = cmd.index("-j")
    assert cmd[j_idx + 1] == "8"
    # -j musi być przed pozytywnym argumentem (plik na końcu).
    assert j_idx + 1 < len(cmd) - 1


def test_build_restore_command_pgdump_requires_dump_path():
    with pytest.raises(ValueError, match="dump_in_container"):
        build_restore_command(format="pgdump", container_id="abc")


def test_build_restore_command_unknown_raises():
    with pytest.raises(ValueError):
        build_restore_command(
            format="tar", container_id="x", db_user="bpp", db_name="bpp"
        )


def test_resolve_jobs_uses_env_override(monkeypatch):
    from bpp.management.commands._run_site_helpers.restore import _resolve_jobs

    monkeypatch.setenv("BPP_RESTORE_JOBS", "12")
    assert _resolve_jobs() == 12


def test_resolve_jobs_clamps_to_minimum_1(monkeypatch):
    from bpp.management.commands._run_site_helpers.restore import _resolve_jobs

    monkeypatch.setenv("BPP_RESTORE_JOBS", "0")
    assert _resolve_jobs() == 1


def test_resolve_jobs_invalid_env_falls_back_to_default(monkeypatch):
    from bpp.management.commands._run_site_helpers.restore import _resolve_jobs

    monkeypatch.setenv("BPP_RESTORE_JOBS", "not-a-number")
    n = _resolve_jobs()
    assert n >= 1
    assert n <= 8


def test_resolve_jobs_default_is_capped(monkeypatch):
    from bpp.management.commands._run_site_helpers.restore import _resolve_jobs

    monkeypatch.delenv("BPP_RESTORE_JOBS", raising=False)
    n = _resolve_jobs()
    assert 1 <= n <= 8


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
        pg_host="x",
        pg_port=1,
        redis_host="x",
        redis_port=2,
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
        pg_host="x",
        pg_port=1,
        redis_host="x",
        redis_port=2,
        with_celery=False,
        dump_label="baseline",
    )
    assert "disabled" in text.lower() or "wyłączone" in text.lower()


def test_banner_dump_label_path():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="x",
        admin_url="y",
        admin_user="a",
        admin_pass="b",
        pg_host="x",
        pg_port=1,
        redis_host="y",
        redis_port=2,
        with_celery=False,
        dump_label="/path/to/dump.sql.gz",
    )
    assert "/path/to/dump.sql.gz" in text


def test_format_agent_help_contains_token_path_and_url():
    from bpp.management.commands._run_site_helpers.banner import (
        format_agent_help,
    )

    text = format_agent_help(
        appserver_url="http://localhost:54321",
        token_path="/tmp/foo/.run_site_token",
        port_path="/tmp/foo/.run_site_port",
    )
    assert "/tmp/foo/.run_site_token" in text
    assert "/tmp/foo/.run_site_port" in text
    assert "http://localhost:54321" in text
    assert "__run_site_autologin__" in text
    assert "curl" in text


def test_format_agent_help_snippet_uses_port_file_not_hardcoded():
    """Snippet czyta port z `.run_site_port`, nie hardcode'uje URL-a z appserver_url.

    Pattern z dotfile'a (PORT=$(cat ...)) jest reusable między runami —
    port się zmienia, ale polecenie zostaje to samo. Hardcoded URL by się
    rozjechał przy następnym uruchomieniu run_site.
    """
    from bpp.management.commands._run_site_helpers.banner import (
        format_agent_help,
    )

    text = format_agent_help(
        appserver_url="http://localhost:54321",
        token_path=".run_site_token",
        port_path=".run_site_port",
    )
    # Snippet używa $PORT zamiast hardcode'owanego ":54321" w URL-u curl-a.
    # Filtrujemy tylko linie snippetu (4-spacjowe wcięcie), żeby nie
    # łapać nagłówka "Auto-login dla agenta (WebFetch / curl)".
    curl_lines = [
        line
        for line in text.splitlines()
        if line.startswith("    ") and "curl" in line
    ]
    assert curl_lines, "snippet musi mieć linie curl-a"
    for line in curl_lines:
        assert "localhost:$PORT" in line, (
            f"curl powinien używać $PORT z dotfile'a, jest: {line!r}"
        )
        assert ":54321" not in line, (
            f"curl nie powinien hardcode'ować portu z appserver_url: {line!r}"
        )


def test_format_agent_help_no_box_drawing_chars_in_snippet():
    """Snippet do skopiowania (linie zaczynające się od ' ' x4) — bez box chars.

    Box-drawing chars dopuszczamy tylko w nagłówku/separatorze, ale nie
    w samym kodzie do copy-paste (terminale czasem mangą je przy
    zaznaczaniu i kopiowanie się sypie).
    """
    from bpp.management.commands._run_site_helpers.banner import (
        format_agent_help,
    )

    text = format_agent_help(
        appserver_url="http://localhost:8080",
        token_path=".run_site_token",
        port_path=".run_site_port",
    )
    snippet_lines = [line for line in text.splitlines() if line.startswith("    ")]
    assert snippet_lines, "agent help musi zawierać snippet z 4-spacjowym wcięciem"
    for line in snippet_lines:
        for ch in line:
            assert ord(ch) < 0x80, f"non-ASCII char w copy-paste snippet: {line!r}"


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


# ── log_multiplexer ─────────────────────────────────────────────────────


def test_log_multiplexer_writes_lines_with_prefix():
    import io

    from bpp.management.commands._run_site_helpers.log_multiplexer import (
        COLOR_CYAN,
        LogMultiplexer,
    )

    out = io.StringIO()
    mux = LogMultiplexer(output=out, use_color=False)
    stream = io.BytesIO(b"hello\nworld\n")
    mux.add_stream("web", COLOR_CYAN, stream)
    mux.join(timeout=2.0)

    text = out.getvalue()
    assert "web | hello\n" in text
    assert "web | world\n" in text


def test_log_multiplexer_pads_names_to_widest():
    import io

    from bpp.management.commands._run_site_helpers.log_multiplexer import (
        COLOR_CYAN,
        COLOR_GREEN,
        LogMultiplexer,
    )

    out = io.StringIO()
    mux = LogMultiplexer(output=out, use_color=False)
    # Add szerszą nazwę PRZED czytaniem — żeby wszystkie linie miały tę samą
    # szerokość kolumny od początku.
    mux.add_stream("celery", COLOR_GREEN, io.BytesIO(b""))
    mux.add_stream("web", COLOR_CYAN, io.BytesIO(b"hi\n"))
    mux.join(timeout=2.0)

    text = out.getvalue()
    # "web" powinno być wyrównane do 6 znaków (długość "celery").
    assert "web    | hi\n" in text


def test_log_multiplexer_emits_color_when_enabled():
    import io

    from bpp.management.commands._run_site_helpers.log_multiplexer import (
        COLOR_CYAN,
        COLOR_RESET,
        LogMultiplexer,
    )

    out = io.StringIO()
    mux = LogMultiplexer(output=out, use_color=True)
    mux.add_stream("web", COLOR_CYAN, io.BytesIO(b"x\n"))
    mux.join(timeout=2.0)

    text = out.getvalue()
    assert COLOR_CYAN in text
    assert COLOR_RESET in text


def test_log_multiplexer_no_color_when_disabled():
    import io

    from bpp.management.commands._run_site_helpers.log_multiplexer import (
        COLOR_CYAN,
        COLOR_RESET,
        LogMultiplexer,
    )

    out = io.StringIO()
    mux = LogMultiplexer(output=out, use_color=False)
    mux.add_stream("web", COLOR_CYAN, io.BytesIO(b"x\n"))
    mux.join(timeout=2.0)

    text = out.getvalue()
    assert COLOR_CYAN not in text
    assert COLOR_RESET not in text


def test_log_multiplexer_handles_invalid_utf8():
    """Linie z nieprawidłowym UTF-8 nie crashują czytnika."""
    import io

    from bpp.management.commands._run_site_helpers.log_multiplexer import (
        COLOR_CYAN,
        LogMultiplexer,
    )

    out = io.StringIO()
    mux = LogMultiplexer(output=out, use_color=False)
    mux.add_stream("pg", COLOR_CYAN, io.BytesIO(b"ok\n\xff\xfe\nzzz\n"))
    mux.join(timeout=2.0)

    text = out.getvalue()
    assert "pg | ok\n" in text
    assert "pg | zzz\n" in text


def test_spawn_pg_logs_invokes_docker_logs_follow():
    """spawn_pg_logs woła `docker logs -f --tail 0 <id>`."""
    import subprocess
    from unittest.mock import patch

    from bpp.management.commands._run_site_helpers.processes import spawn_pg_logs

    with patch.object(subprocess, "Popen") as mock_popen:
        spawn_pg_logs("abc123")
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["docker", "logs", "-f", "--tail", "0", "abc123"]
        kwargs = mock_popen.call_args[1]
        assert kwargs.get("stdout") == subprocess.PIPE
        assert kwargs.get("stderr") == subprocess.STDOUT


def test_spawn_runserver_sets_pythonunbuffered():
    """spawn_runserver wymusza PYTHONUNBUFFERED=1, inaczej multiplekser
    nie widzi linii dopóki bufor 4KB się nie zapełni."""
    import subprocess
    from unittest.mock import patch

    from bpp.management.commands._run_site_helpers.processes import spawn_runserver

    with patch.object(subprocess, "Popen") as mock_popen:
        spawn_runserver(8000, env={"FOO": "bar"})
        kwargs = mock_popen.call_args[1]
        assert kwargs["env"]["PYTHONUNBUFFERED"] == "1"
        assert kwargs["env"]["FOO"] == "bar"
        assert kwargs["stdout"] == subprocess.PIPE


def test_spawn_celery_uses_pipe_and_unbuffered():
    """spawn_celery odpina logi na PIPE (czytane przez multiplekser)."""
    import subprocess
    from unittest.mock import patch

    from bpp.management.commands._run_site_helpers.processes import spawn_celery

    with patch.object(subprocess, "Popen") as mock_popen:
        spawn_celery(env={"X": "y"})
        kwargs = mock_popen.call_args[1]
        assert kwargs["env"]["PYTHONUNBUFFERED"] == "1"
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.STDOUT
        cmd = mock_popen.call_args[0][0]
        assert "--pool=solo" in cmd


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
        json.dumps({"username": "bob", "pbn_token": "tok", "pbn_token_updated": None})
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
        json.dumps({"username": "alice", "pbn_token": "tok", "pbn_token_updated": None})
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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("~/bpp-deploy", "~/bpp-deploy"),
        ("~", "~"),
        ("~/path with space", "~/'path with space'"),
        ("/abs/path", "/abs/path"),
        ("/path with space", "'/path with space'"),
        ("relative", "relative"),
    ],
)
def test_quote_remote_path_preserves_tilde(raw, expected):
    # Bash nie rozwija ~ wewnątrz cudzysłowów — wiodące ~/ musi
    # zostać poza quotem, inaczej cd na zdalnym hoście pójdzie do
    # dosłownego katalogu o nazwie ~/bpp-deploy.
    assert _quote_remote_path(raw) == expected


def test_dump_via_ssh_does_not_quote_leading_tilde():
    """Regresja: shlex.quote("~/x") tworzyło '~/x' i bash nie rozwijał ~."""
    captured: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        captured.append(cmd)

        class _R:
            returncode = 0
            stdout = ""
            stderr = "boom"

        return _R()

    logs: list[str] = []
    with patch(
        "bpp.management.commands._run_site_helpers.pbn_token.subprocess.run",
        side_effect=fake_run,
    ):
        fetch_pbn_token_via_ssh(
            _src(),
            remote_deploy_path="~/bpp-deploy",
            remote_compose_service="appserver",
            local_env={},
            log=logs.append,
            cache_path=None,
        )

    assert captured, "ssh nie został wywołany"
    ssh_cmd = captured[0]
    assert ssh_cmd[0] == "ssh"
    remote = ssh_cmd[2]
    assert "cd ~/" in remote
    assert "'~/bpp-deploy'" not in remote
