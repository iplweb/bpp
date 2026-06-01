"""Guard: ciężkie zależności (numpy/openpyxl) NIE ładują się w grafie importu
BPP poza adminem Django.

Kontekst (PR „reduce memory footprint"): numpy (~30 MB RSS) i openpyxl były
wciągane eager już przy ``django.setup()`` w KAŻDYM procesie (web/ASGI + workery
Celery + beat + denorm), bo moduły admin/models importowały je na poziomie
modułu — głównie przez ``import_common.normalization`` (``from numpy import
isnan`` dla jednego skalara) oraz funkcje xlsx (openpyxl -> numpy).

Te importy zostały odroczone (math.isnan, lokalne importy openpyxl, PEP 562
``__getattr__`` w bpp.util). Ten test pilnuje, że nikt nie przywróci eager-importu
w grafie setupu poza adminem. Sam admin Django (autodiscover) i tak ładuje
openpyxl/numpy przez django-import-export (twarda podłoga biblioteki) — dlatego
test neutralizuje autodiscover, symulując proces workera, który admina nie
serwuje. To jest dokładnie warunek, pod którym worker Celery z pominiętym
autodiscover schodzi z ~154 MB do ~130 MB bez numpy/openpyxl.
"""

import os
import subprocess
import sys

from django.conf import settings

import bpp

_SUBPROCESS = """
import sys

# Symuluj proces, który NIE serwuje admina (worker/beat/denorm): pomiń
# admin.autodiscover, który przez django-import-export wciąga openpyxl/numpy.
import django.contrib.admin.apps as admin_apps
admin_apps.AdminConfig.ready = admin_apps.SimpleAdminConfig.ready

import django
django.setup()

heavy = [m for m in ("numpy", "openpyxl", "pandas") if m in sys.modules]
assert not heavy, f"Ciezkie moduly zaladowane eager przy setup (poza adminem): {heavy}"

# Publiczne API bpp.util nadal dziala (PEP 562 __getattr__) i dopiero TERAZ
# leniwie ciagnie openpyxl.
import bpp.util
assert callable(bpp.util.worksheet_columns_autosize)
assert callable(bpp.util.sanitize_xlsx_row)
assert "openpyxl" in sys.modules, "dostep do funkcji xlsx powinien zaladowac openpyxl"

print("LAZY_OK")
"""


def test_heavy_imports_absent_from_non_admin_setup_graph():
    src_dir = os.path.dirname(os.path.dirname(bpp.__file__))
    env = dict(os.environ)
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
    env["DJANGO_SETTINGS_MODULE"] = settings.SETTINGS_MODULE or env.get(
        "DJANGO_SETTINGS_MODULE", "django_bpp.settings.local"
    )
    # Nie pozwól, by .env nadpisał wstrzyknięte przez testcontainery porty DB.
    env.setdefault("DJANGO_BPP_SKIP_DOTENV", "1")

    result = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "LAZY_OK" in result.stdout, result.stdout
