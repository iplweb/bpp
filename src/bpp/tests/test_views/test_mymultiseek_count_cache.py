"""Cache agregatów strony wyników multiseek (count + sumy).

Stronicowanie wyników nie może powtarzać drogiego COUNT (DISTINCT przy
joinie do bpp_autorzy_mat) przy każdej stronie tego samego zapytania —
agregaty są cache'owane per (formularz, removed, print-removed,
zalogowanie, uczelnia). Zmiana któregokolwiek z tych wejść przelicza.

Uwaga: settings testowe mają DummyCache — testy podmieniają default na
LocMemCache fixture'em `settings`.
"""

import json
from decimal import Decimal

import pytest
from django.conf import settings as django_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation
from multiseek.logic import STARTS_WITH
from multiseek.views import MULTISEEK_SESSION_KEY, MULTISEEK_SESSION_KEY_REMOVED

from bpp.models import Rekord
from bpp.tests.util import any_ciagle

TYTUL_PREFIX = "CCache multiseek"
TABLE_REPORT_TYPE = "1"


def _ustaw_filtr(client, value, report_type=TABLE_REPORT_TYPE):
    with translation.override(django_settings.LANGUAGE_CODE):
        operator = str(STARTS_WITH)

    session = client.session
    session[MULTISEEK_SESSION_KEY] = json.dumps(
        {
            "form_data": [
                None,
                {
                    "field": "Tytuł pracy",
                    "operator": operator,
                    "value": value,
                    "prev_op": None,
                },
            ],
            "ordering": {},
            "report_type": report_type,
        }
    )
    session.save()


def _agregaty_sql(ctx):
    return [
        q["sql"]
        for q in ctx.captured_queries
        if "bpp_rekord_mat" in q["sql"]
        and ("COUNT(" in q["sql"].upper() or "SUM(" in q["sql"].upper())
    ]


@pytest.fixture
def locmem_cache(settings):
    # Podmień tylko alias "default" (testowo DummyCache); constance_cache
    # zostaje bez zmian (django-constance odrzuca backendy lokalne).
    caches = dict(settings.CACHES)
    caches["default"] = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    settings.CACHES = caches
    from django.core.cache import cache

    cache.clear()
    yield cache
    cache.clear()


@pytest.fixture
def dwa_rekordy(standard_data):
    a = any_ciagle(
        tytul_oryginalny=f"{TYTUL_PREFIX} alfa",
        rok=2024,
        impact_factor=Decimal("1.500"),
    )
    b = any_ciagle(
        tytul_oryginalny=f"{TYTUL_PREFIX} beta",
        rok=2023,
        impact_factor=Decimal("2.500"),
    )
    return a, b


@pytest.mark.django_db
def test_drugie_wejscie_nie_liczy_agregatow_ponownie(client, dwa_rekordy, locmem_cache):
    _ustaw_filtr(client, TYTUL_PREFIX)

    res1 = client.get(reverse("multiseek:results"))
    assert res1.context["paginator_count"] == 2

    with CaptureQueriesContext(connection) as ctx:
        res2 = client.get(reverse("multiseek:results"))

    assert res2.context["paginator_count"] == 2
    assert res2.context["sumy"]["impact_factor__sum"] == Decimal("4.000")
    assert _agregaty_sql(ctx) == []


@pytest.mark.django_db
def test_zmiana_formularza_przelicza(client, dwa_rekordy, locmem_cache):
    _ustaw_filtr(client, TYTUL_PREFIX)
    assert client.get(reverse("multiseek:results")).context["paginator_count"] == 2

    _ustaw_filtr(client, f"{TYTUL_PREFIX} beta")
    assert client.get(reverse("multiseek:results")).context["paginator_count"] == 1


@pytest.mark.django_db
def test_wyrzucenie_rekordu_przelicza(client, dwa_rekordy, locmem_cache):
    _ustaw_filtr(client, TYTUL_PREFIX)
    assert client.get(reverse("multiseek:results")).context["paginator_count"] == 2

    rekord = Rekord.objects.get_original(dwa_rekordy[0])
    session = client.session
    session[MULTISEEK_SESSION_KEY_REMOVED] = [list(rekord.pk)]
    session.save()

    assert client.get(reverse("multiseek:results")).context["paginator_count"] == 1


@pytest.mark.django_db
def test_zalogowanie_ma_osobny_cache(client, admin_client, dwa_rekordy, locmem_cache):
    """Anonim i zalogowany mają osobne klucze (ukryte statusy zależą od
    zalogowania) — wpis anonima nie może obsłużyć admina."""
    _ustaw_filtr(client, TYTUL_PREFIX)
    assert client.get(reverse("multiseek:results")).context["paginator_count"] == 2

    _ustaw_filtr(admin_client, TYTUL_PREFIX)
    res = admin_client.get(reverse("multiseek:results"))
    assert res.context["paginator_count"] == 2
