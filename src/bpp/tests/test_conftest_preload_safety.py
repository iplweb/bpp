"""Regression guard for the ``pytest-testcontainers-django`` conftest preload.

The plugin preloads the rootdir ``conftest.py`` from a ``tryfirst``
``pytest_load_initial_conftests`` hook — i.e. *before* ``pytest-django``
runs ``django.setup()``.  At that moment Django settings may already be
configured (``DJANGO_SETTINGS_MODULE`` is set via ``--ds``) but the app
registry is **not** populated yet.

If any module reachable from the rootdir conftest's ``from fixtures import *``
imports or defines a Django model at top level, executing that class body
calls ``apps.get_containing_app_config()`` → ``AppRegistryNotReady:
Apps aren't loaded yet`` — and the plugin logs a full, alarming traceback
("preloading rootdir conftest.py raised; continuing") at the end of every run.

Model-bearing fixture modules therefore belong in ``pytest_plugins`` (loaded
*after* ``django.setup()``), never in the eager ``from fixtures import *``
chain.  This test reproduces the exact bootstrap state in a clean subprocess
and asserts the rootdir conftest imports without touching the app registry.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Mimics the plugin's preload: configure settings (read DJANGO_SETTINGS_MODULE)
# WITHOUT calling django.setup(), then import the rootdir conftest exactly the
# way the preload does.  A top-level model import anywhere in the
# `from fixtures import *` chain blows up here with AppRegistryNotReady.
_PRELOAD_SNIPPET = """
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.test")

from django.conf import settings

settings.INSTALLED_APPS  # force lazy settings load; does NOT populate apps

import django.apps

assert django.apps.apps.ready is False, (
    "precondition failed: app registry is already populated; this test must "
    "run the import BEFORE django.setup() to mirror the plugin preload"
)

import conftest  # noqa: F401  -- the rootdir conftest the plugin preloads
"""


def test_rootdir_conftest_imports_before_django_setup():
    env = {
        **os.environ,
        # Match pytest.ini's `pythonpath = src` plus the rootdir for `conftest`.
        "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / "src")]),
        "DJANGO_BPP_TESTING": "1",
    }
    result = subprocess.run(
        [sys.executable, "-c", _PRELOAD_SNIPPET],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Importing the rootdir conftest before django.setup() failed — a "
        "top-level Django model import leaked into the `from fixtures import *` "
        "preload chain. Move it into a pytest_plugins module instead.\n\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _pytest_plugins_of(conftest_path: Path) -> list[str]:
    """Statically extract the ``pytest_plugins`` list literal from a conftest.

    Uses ``ast`` instead of importing the module: the rootdir conftest runs a
    ``make assets`` check and ``from fixtures import *`` at import time, and
    ``src/conftest.py`` installs monkey-patches — none of which we want to
    trigger just to read a list of strings.
    """
    tree = ast.parse(conftest_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytest_plugins" for t in node.targets
        ):
            return [el.value for el in node.value.elts if isinstance(el, ast.Constant)]
    return []


# Probe run in a clean subprocess that mirrors the plugin preload bootstrap
# (settings configured, ``django.setup()`` NOT called). For each plugin module
# named on argv it prints ``<module>\tOK`` if it imports cleanly or
# ``<module>\tUNSAFE: <exc>`` if importing it touches the unpopulated app
# registry. A module that is UNSAFE here cannot be reliably registered from the
# rootdir conftest's ``pytest_plugins`` (whose loading races ``django.setup()``)
# and therefore MUST also be registered in ``src/conftest.py`` (loaded AFTER
# ``django.setup()``), or its fixtures silently vanish — exactly the
# ``fixture 'site1' not found`` class of failure.
_PLUGIN_IMPORT_PROBE = """
import importlib
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")

from django.conf import settings

settings.INSTALLED_APPS  # force lazy settings load; does NOT populate apps

import django.apps

assert django.apps.apps.ready is False, (
    "precondition failed: app registry is already populated"
)

for module in sys.argv[1:]:
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 -- any failure means preload-unsafe
        print(f"{module}\\tUNSAFE: {type(exc).__name__}: {exc}")
    else:
        print(f"{module}\\tOK")
"""


def test_model_bearing_plugins_are_registered_post_django_setup():
    """Every preload-unsafe fixture plugin in the rootdir conftest must also be
    registered in ``src/conftest.py`` (the post-``django.setup()`` list).

    The rootdir conftest's ``pytest_plugins`` is loaded during the
    ``pytest-testcontainers-django`` preload, which races ``django.setup()``.
    A model-bearing module registered ONLY there fails to import (its fixtures
    never register) and every test requesting them errors at setup with
    ``fixture '...' not found``. ``src/conftest.py`` is the safety net that
    registers such modules once the app registry is ready.
    """
    root_plugins = _pytest_plugins_of(REPO_ROOT / "conftest.py")
    src_plugins = set(_pytest_plugins_of(REPO_ROOT / "src" / "conftest.py"))
    assert root_plugins, "could not parse pytest_plugins from rootdir conftest.py"

    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / "src")]),
        "DJANGO_BPP_TESTING": "1",
    }
    result = subprocess.run(
        [sys.executable, "-c", _PLUGIN_IMPORT_PROBE, *root_plugins],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "plugin import probe crashed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    unsafe = {
        line.split("\t", 1)[0]
        for line in result.stdout.splitlines()
        if "\tUNSAFE:" in line
    }
    offenders = sorted(unsafe - src_plugins)
    assert not offenders, (
        "These fixture plugin modules import Django models at top level and are "
        "registered ONLY in the rootdir conftest.py's pytest_plugins, so their "
        "fixtures silently fail to register under the testcontainers preload "
        "(tests requesting them error with `fixture '...' not found`). Add them "
        "to src/conftest.py's pytest_plugins (loaded after django.setup()), "
        "alongside fixtures.pbn_api / fixtures.wydawnictwa:\n  "
        + "\n  ".join(offenders)
        + f"\n\n--- probe output ---\n{result.stdout}"
    )
