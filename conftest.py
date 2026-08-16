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

    BPP_SKIP_ASSETS_BUILD=1 pomija ten krok. Używane w CI: obraz
    test-runner ma zapieczone CSS + .mo (Dockerfile, stage test-runner),
    więc każdy z N shardów odpalający `make assets` to tylko narzut —
    a w praktyce robi pełny `yarn install` + `grunt build`, bo Dockerfile
    nie zostawia w obrazie sentinela `node_modules/.installed`.

    Pod xdistem budujemy TYLKO w kontrolerze. `pytest_configure` odpala się
    w kontrolerze i dodatkowo w każdym workerze, więc `-n auto` na dziesięciu
    rdzeniach dawało jedenaście równoległych `make assets` (zmierzone).
    Inkrementalność `make` tego nie ratuje: wszystkie procesy sprawdzają
    sentinel `.grunt-build-stamp` w tej samej chwili, każdy niezależnie
    stwierdza „nieaktualny" i wszystkie wchodzą w `grunt build` naraz —
    pisząc do TYCH SAMYCH plików wyjściowych. To był zarówno skok obciążenia
    (kilkanaście równoległych sass + esbuild), jak i wyścig na zapisie.

    Kolejność jest bezpieczna: kontroler kończy `pytest_configure`, zanim
    xdist rozstawi workery w `pytest_sessionstart`, więc assety są gotowe,
    nim którykolwiek worker zacznie renderować. Zweryfikowane empirycznie na
    celowo nieaktualnym sentinelu — jeden build, sentinel odświeżony, testy
    zielone.

    Sentinel psuje też `npx grunt build` odpalany RĘCZNIE: buduje pliki, ale
    nie dotyka `.grunt-build-stamp` (robi to dopiero reguła w Makefile), więc
    kolejny `make assets` i tak przebuduje. Do odświeżenia assetów używaj
    `make assets`, nie gołego grunta.
    """
    import os
    import sys

    if hasattr(config, "workerinput"):
        return

    if os.environ.get("BPP_SKIP_ASSETS_BUILD"):
        return

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

# UWAGA: tu wolno importować WYŁĄCZNIE symbole z modułów wolnych od Django
# (czyli `fixtures.const`). `pytest-testcontainers-django` preloaduje ten
# rootdir-owy conftest w hooku `pytest_load_initial_conftests` (tryfirst),
# ZANIM `pytest-django` zrobi `django.setup()`. Każdy top-levelowy import
# modelu w łańcuchu `from fixtures import *` wybucha wtedy
# `AppRegistryNotReady`. Moduły z fiksturami importującymi modele
# (`pbn_api`, `wydawnictwa`) są zarejestrowane jako pytest pluginy w
# `src/conftest.py` (ładowane PO `django.setup()`).
# Regresja-guard: src/bpp/tests/test_conftest_preload_safety.py.
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
