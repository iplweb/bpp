"""Start aplikacji nie może wciągać ciężkich bibliotek.

Te pakiety są importowane leniwie (wewnątrz funkcji, które ich używają),
bo każdy z nich kosztował dziesiątki–setki ms przy KAŻDYM starcie
appservera, workera Celery i workera xdist:

* ``ortools`` (+ ``pandas``) — ``ewaluacja_optymalizacja.tasks.optimization``,
* ``pandas``/``numpy`` — ``import_polon.utils``,
* ``weasyprint``/``django_weasyprint`` — ``raport_slotow.views.autor``,
* ``xhtml2pdf`` (+ reportlab, pypdf) — ``oswiadczenia.tasks._pisa``,
* ``idutils`` — ``zglos_publikacje.identyfikatory``.

Test odpala start w OSOBNYM procesie (w procesie pytest wszystko jest już
dawno zaimportowane przez inne testy) i sprawdza ``sys.modules``. Jeśli
padnie, ktoś dopisał import na górze modułu ładowanego przy starcie —
przenieś go do funkcji, która go potrzebuje. Spec:
docs/deweloper/spec-testcontainers-pg-szybciej-2026-11.md.
"""

import json
import os
import subprocess
import sys

LENIWE = (
    "ortools",
    "pandas",
    "weasyprint",
    "django_weasyprint",
    "xhtml2pdf",
    "idutils",
)

SKRYPT = """
import json, sys
import django
django.setup()
from django.urls import get_resolver
get_resolver().url_patterns
import django_bpp.celery_tasks as ct
ct.app.loader.import_default_modules()
print(json.dumps(sorted({m.split(".")[0] for m in sys.modules})))
"""


def test_start_aplikacji_nie_importuje_ciezkich_bibliotek():
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(p for p in sys.path if p),
        "DJANGO_SETTINGS_MODULE": "django_bpp.settings.test",
    }
    wynik = subprocess.run(
        [sys.executable, "-c", SKRYPT],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert wynik.returncode == 0, wynik.stderr[-3000:]
    zaladowane = set(json.loads(wynik.stdout.strip().splitlines()[-1]))
    assert not (zaladowane & set(LENIWE)), (
        "Start aplikacji zaimportował: "
        f"{sorted(zaladowane & set(LENIWE))} — przenieś import do funkcji."
    )
