"""Testy command-line interface komendy run_site (no Docker required)."""

import contextlib
from io import StringIO

import pytest
from django.core.management import call_command


def test_run_site_help_does_not_crash():
    """Sanity check że komenda jest zarejestrowana."""
    # Django's argparse `--help` writes via sys.stdout (nie self.stdout),
    # więc trzeba przejąć sys.stdout — `stdout=out` w call_command nie
    # zadziała dla `--help`.
    out = StringIO()
    with pytest.raises(SystemExit) as exc_info:
        with contextlib.redirect_stdout(out):
            call_command("run_site", "--help", stdout=out)
    assert exc_info.value.code == 0
    text = out.getvalue()
    assert "--from-dump" in text
    assert "--with-celery" in text
    assert "--no-browser" in text
    assert "--port" in text
    assert "--reuse" in text


def test_run_site_invalid_dump_path_raises(tmp_path):
    """Nieistniejący --from-dump rzuca CommandError od razu."""
    from django.core.management.base import CommandError

    nonexistent = tmp_path / "no-such-file.sql"
    with pytest.raises(CommandError, match="nie istnieje"):
        call_command("run_site", "--from-dump", str(nonexistent), "--dry-run")


def test_run_site_unsupported_format_raises(tmp_path):
    """Plik o nieobsługiwanym rozszerzeniu rzuca CommandError."""
    from django.core.management.base import CommandError

    bad = tmp_path / "dump.tar"
    bad.write_text("x")
    with pytest.raises(CommandError, match="format"):
        call_command("run_site", "--from-dump", str(bad), "--dry-run")


def test_run_site_dry_run_with_valid_sql_succeeds(tmp_path):
    """Dry-run z poprawnym .sql kończy się bez błędów."""
    sql = tmp_path / "valid.sql"
    sql.write_text("SELECT 1;")
    call_command("run_site", "--from-dump", str(sql), "--dry-run")


def test_autologin_token_file_write_and_remove(tmp_path, monkeypatch):
    """Helper zapisuje token z chmod 600 i kasuje go bezpiecznie."""
    import stat

    from bpp.management.commands import run_site as run_site_mod

    monkeypatch.setattr(
        run_site_mod, "_autologin_token_path", lambda: tmp_path / ".run_site_token"
    )

    path = run_site_mod._write_autologin_token_file("sekret-abc123")
    assert path.read_text() == "sekret-abc123"
    # chmod 600 — tylko właściciel może czytać/pisać
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"oczekiwano 0o600, jest {oct(mode)}"

    run_site_mod._remove_autologin_token_file()
    assert not path.exists()

    # Drugie wywołanie (np. atexit po finally) nie wybucha:
    run_site_mod._remove_autologin_token_file()


def test_port_file_write_and_remove(tmp_path, monkeypatch):
    """Helper zapisuje numer portu i kasuje go bezpiecznie."""
    from bpp.management.commands import run_site as run_site_mod

    monkeypatch.setattr(run_site_mod, "_port_path", lambda: tmp_path / ".run_site_port")

    path = run_site_mod._write_port_file(53715)
    assert path.read_text() == "53715"

    run_site_mod._remove_port_file()
    assert not path.exists()

    # Drugie wywołanie (atexit po finally) nie wybucha:
    run_site_mod._remove_port_file()


def test_pg_port_file_write_and_remove(tmp_path, monkeypatch):
    """Helper zapisuje port PG (testcontainers) i kasuje go bezpiecznie."""
    from bpp.management.commands import run_site as run_site_mod

    monkeypatch.setattr(
        run_site_mod, "_pg_port_path", lambda: tmp_path / ".run_site_pg_port"
    )

    path = run_site_mod._write_pg_port_file(54322)
    assert path.read_text() == "54322"

    run_site_mod._remove_pg_port_file()
    assert not path.exists()

    # Drugie wywołanie (atexit po finally) nie wybucha:
    run_site_mod._remove_pg_port_file()


def test_redis_port_file_write_and_remove(tmp_path, monkeypatch):
    """Helper zapisuje port Redisa (testcontainers) i kasuje go bezpiecznie."""
    from bpp.management.commands import run_site as run_site_mod

    monkeypatch.setattr(
        run_site_mod,
        "_redis_port_path",
        lambda: tmp_path / ".run_site_redis_port",
    )

    path = run_site_mod._write_redis_port_file(54323)
    assert path.read_text() == "54323"

    run_site_mod._remove_redis_port_file()
    assert not path.exists()

    # Drugie wywołanie (atexit po finally) nie wybucha:
    run_site_mod._remove_redis_port_file()
