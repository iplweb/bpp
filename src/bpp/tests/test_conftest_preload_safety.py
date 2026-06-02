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
