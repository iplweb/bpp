import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils.translation import activate


def pytest_configure(config):
    """Ensure frontend assets (CSS + .mo) are built before tests run.

    BPP UI depends on built assets; there is no "pure Python" mode.
    `make` handles incremental builds via timestamp deps, so this is
    a no-op when assets are up to date.

    UV_NO_SYNC=1 prevents the `uv run` calls inside Makefile targets
    (e.g. `compilemessages`) from re-syncing and stripping dev extras
    like `testcontainers` from the venv. Tests are expected to run in
    a venv pre-synced with `uv sync --all-extras`.
    """
    import os
    import sys

    repo_root = Path(__file__).parent
    env = {**os.environ, "UV_NO_SYNC": "1"}
    result = subprocess.run(
        ["make", "assets"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(f"\n=== `make assets` failed (exit {result.returncode}) ===\n")
        if result.stdout:
            sys.stderr.write("--- stdout ---\n")
            sys.stderr.write(result.stdout)
            if not result.stdout.endswith("\n"):
                sys.stderr.write("\n")
        if result.stderr:
            sys.stderr.write("--- stderr ---\n")
            sys.stderr.write(result.stderr)
            if not result.stderr.endswith("\n"):
                sys.stderr.write("\n")
        sys.stderr.write("=" * 50 + "\n")
        pytest.exit(
            f"make assets failed (exit {result.returncode}) — see output above",
            returncode=2,
        )


# Load fixtures from submodules - must be at top-level conftest per pytest requirements
pytest_plugins = [
    "fixtures.conftest_models",
    "fixtures.conftest_multisite",
    "fixtures.conftest_publications",
    "fixtures.conftest_system",
    "fixtures.conftest_browser",
    "fixtures.conftest_disciplines",
]

from fixtures import *  # noqa


@pytest.fixture(scope="session")
def today():
    from django.utils import timezone

    return timezone.now().date()


@pytest.fixture(scope="session")
def yesterday(today):
    return today - timedelta(days=1)


@pytest.fixture(scope="session")
def tommorow(today):
    return today + timedelta(days=1)


@pytest.fixture(autouse=True)
def set_default_language():
    activate("en")
