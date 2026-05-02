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
