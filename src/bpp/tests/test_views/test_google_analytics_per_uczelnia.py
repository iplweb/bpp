"""Snippet Google Analytics NIE może być współdzielony między uczelniami.

``GOOGLE_ANALYTICS_PROPERTY_ID`` jest per-uczelnia (context processor
``bpp.context_processors.constance_config`` czyta go z ``request._uczelnia``),
a ``base.html`` przez pewien czas cache'owało ten fragment pod GLOBALNYM
kluczem ``{% cache 3600 google %}`` — bez ``vary_on``. Skutek w instalacji
wielo-uczelnianej: pierwszy odwiedzający uczelni A rozgrzewał fragment swoim
identyfikatorem, a przez następną godzinę goście uczelni B dostawali snippet
uczelni A — ruch uczelni B raportował się do konta Google uczelni A.
"""

import pytest
from django.template.loader import render_to_string

from fixtures.conftest_multisite import make_request_for_site

GA_UCZELNIA1 = "G-UCZELNIA1XX"
GA_UCZELNIA2 = "G-UCZELNIA2XX"


def _renderuj_stopke(site):
    """Wyrenderuj ``base.html`` jako anonim z zaakceptowanym cookielaw."""
    request = make_request_for_site(site)
    request.COOKIES["cookielaw_accepted"] = "1"
    return render_to_string("base.html", request=request)


@pytest.mark.django_db
def test_snippet_ga_nie_wycieka_miedzy_uczelniami(
    settings, site1, site2, uczelnia1, uczelnia2
):
    """Każda domena dostaje WŁASNE ID Google Analytics, nie cudze."""
    settings.ALLOWED_HOSTS = ["*"]
    # Domyślny cache w testach to DummyCache — nie odtworzyłby błędu, bo
    # nigdy niczego nie zapamiętuje. Produkcja ma Redis, więc podstawiamy
    # backend, który faktycznie przechowuje fragmenty.
    settings.CACHES = {
        **settings.CACHES,
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    }

    uczelnia1.google_analytics_property_id = GA_UCZELNIA1
    uczelnia1.save(update_fields=["google_analytics_property_id"])
    uczelnia2.google_analytics_property_id = GA_UCZELNIA2
    uczelnia2.save(update_fields=["google_analytics_property_id"])

    # Kolejność ma znaczenie: uczelnia1 „rozgrzewa" cache jako pierwsza.
    html1 = _renderuj_stopke(site1)
    html2 = _renderuj_stopke(site2)

    assert GA_UCZELNIA1 in html1
    assert GA_UCZELNIA2 not in html1

    assert GA_UCZELNIA2 in html2, "uczelnia2 dostała cudzy snippet GA z cache'a"
    assert GA_UCZELNIA1 not in html2, "ID uczelni1 wyciekło na domenę uczelni2"
