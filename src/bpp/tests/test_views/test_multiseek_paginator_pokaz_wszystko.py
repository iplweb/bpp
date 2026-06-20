"""Regresje #377 i #376 dla listwy paginatora multiseeka.

#377 — niezalogowany użytkownik nie mógł wyświetlić całego dorobku autora,
bo przycisk "Pokaż wszystkie" znikał powyżej progu zaszytego w polu
``Uczelnia.wyszukiwanie_rekordy_na_strone_anonim`` (próg podniesiony do 2000).

#376 — etykieta przycisku "Pokaż" → "Wyświetl wszystkie" oraz kolejność
listwy: Razem / Wyświetl wszystkie / Drukuj / CSV / XLS (Wyświetl przed
Drukuj).
"""

import types

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template
from django.test import RequestFactory

from bpp.models import Uczelnia

PAGINATOR_TEMPLATE = "multiseek/paginator.html"

# Renderowanie szablonu sięga do DB (resolver URL-i / lazy auth), więc cały
# moduł działa pod django_db.
pytestmark = pytest.mark.django_db


def _render_paginator(get_params=None, user=None, **overrides):
    """Renderuje listwę paginatora w izolacji (bez DB / context processorów).

    ``max_rows`` to próg widoczności "Wyświetl wszystkie" — w realnym
    szablonie podawany z ``uczelnia.wyszukiwanie_rekordy_na_strone_*``.
    """
    request = RequestFactory().get("/multiseek/results/", get_params or {})
    request.user = user or AnonymousUser()
    context = {
        "request": request,
        "is_live": True,
        "paginator_count": 100,
        "max_rows": 2000,
        "multiseek_export_max_rows": 5000,
        "print_removed": False,
        # num_pages=1 => blok {% paginate %} pomijany (nie odpalamy tagu).
        "paginator": types.SimpleNamespace(num_pages=1),
    }
    context.update(overrides)
    return get_template(PAGINATOR_TEMPLATE).render(context)


def test_paginator_pokazuje_wyswietl_wszystkie_ponizej_progu():
    """#377: poniżej progu przycisk jest obecny pod nową etykietą."""
    html = _render_paginator(paginator_count=100, max_rows=2000)
    assert "Wyświetl wszystkie" in html


def test_paginator_ukrywa_wyswietl_wszystkie_powyzej_progu():
    """#377: powyżej progu (max_rows) przycisk znika — to był pierwotny błąd
    przy >500 publikacjach. Przy progu 2000 i 3000 rekordach dalej znika,
    co potwierdza, że to próg steruje widocznością."""
    html = _render_paginator(paginator_count=3000, max_rows=2000)
    assert "Wyświetl wszystkie" not in html


def test_paginator_etykieta_nie_jest_juz_pokaz():
    """#376: stara, myląca etykieta "Pokaż" nie może już występować."""
    html = _render_paginator(paginator_count=100, max_rows=2000)
    assert "Pokaż" not in html


def test_paginator_kolejnosc_wyswietl_przed_drukuj():
    """#376: "Wyświetl wszystkie" musi poprzedzać "Drukuj" na listwie."""
    html = _render_paginator(paginator_count=100, max_rows=2000)
    assert "Wyświetl wszystkie" in html and "Drukuj" in html
    assert html.index("Wyświetl wszystkie") < html.index("Drukuj")


def test_uczelnia_progi_pokaz_wszystkie_default():
    """#377: domyślne progi podniesione do "nowoczesnych" wartości — nowe
    wdrożenia dostają je od ręki, bez ręcznej konfiguracji."""
    uczelnia = Uczelnia()
    assert uczelnia.wyszukiwanie_rekordy_na_strone_anonim == 2000
    assert uczelnia.wyszukiwanie_rekordy_na_strone_zalogowany == 10000
