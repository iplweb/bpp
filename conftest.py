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

    Budowanie stoi pod ZAMKIEM PLIKOWYM, bo „jeden build na przebieg" nie
    wystarcza, gdy przebiegów jest kilka. Dwa `pytest` odpalone naraz w TYM
    SAMYM worktree (druga konsola, agent obok człowieka) to dwa kontrolery —
    przy nieaktualnym sentinelu obydwa ruszyłyby `grunt build` na te same
    pliki wyjściowe. `flock` ustawia je w kolejkę: pierwszy buduje, drugi
    czeka, a po wejściu jego `make assets` jest już pustym przebiegiem —
    podwójne sprawdzenie robi za nas sam `make`, po mtime sentinela. Zamek
    zwalnia jądro przy zamknięciu deskryptora, więc nie da się go osierocić
    nawet przez `kill -9`.

    Zamek NIE serializuje różnych worktree i nie powinien: każdy ma własny
    `.grunt-build-stamp` i własny `staticroot`, więc ich buildy nie kolidują
    na plikach — konkurują wyłącznie o CPU, co jest problemem harmonogramu,
    nie poprawności.

    Zamek obejmuje ścieżkę pytestową, czyli tę, która odpala się sama i
    równolegle. Ręczne `make assets` puszczone w tej samej chwili co testy
    nadal może się z nimi zbiec — to świadome działanie człowieka, nie
    automat, więc nie budujemy pod to maszynerii.
    """
    import fcntl
    import os
    import sys

    if hasattr(config, "workerinput"):
        return

    if os.environ.get("BPP_SKIP_ASSETS_BUILD"):
        return

    repo_root = Path(__file__).parent
    env = {**os.environ, "UV_NO_SYNC": "1"}
    with open(repo_root / ".grunt-build.lock", "w") as zamek:
        fcntl.flock(zamek, fcntl.LOCK_EX)
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
