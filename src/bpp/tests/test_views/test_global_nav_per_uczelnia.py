"""Track 1 (audyt uczelnia 2026-06-04): publiczny ``GlobalNavigationAutocomplete``
zawęża wyniki (jednostki/autorzy/rekordy) do uczelni oglądającego.

Globalna wyszukiwarka nawigacyjna szukała jednostek/autorów/rekordów globalnie
(tylko ``ukryte_statusy``) — R3b objął dedykowane pickery, ten search-box
pominął.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia, Wydzial
from bpp.views.autocomplete.navigation import GlobalNavigationAutocomplete


@pytest.fixture
def jednostka_drugiej_uczelni(db):
    site = baker.make(Site, domain="druga-nav.testserver", name="druga-nav")
    uczelnia2 = Uczelnia.objects.create(skrot="DRN", nazwa="Druga", site=site)
    wydzial = Wydzial.objects.create(uczelnia=uczelnia2, skrot="W2", nazwa="Wydz II")
    return Jednostka.objects.create(
        nazwa="Instytut Testowy Beta", skrot="JDN", wydzial=wydzial, uczelnia=uczelnia2
    )


@pytest.mark.django_db
def test_global_nav_zaweza_jednostki_do_uczelni(
    jednostka, jednostka_drugiej_uczelni, denorms, rf
):
    j1 = jednostka
    j1.nazwa = "Instytut Testowy Alfa"
    j1.save()
    denorms.flush()

    request = rf.get("/?q=Instytut")
    request._uczelnia = j1.uczelnia
    request.user = AnonymousUser()

    view = GlobalNavigationAutocomplete()
    view.request = request
    view.q = "Instytut"

    jednostki = [o for o in view.get_queryset() if isinstance(o, Jednostka)]
    uczelnie = {j.uczelnia_id for j in jednostki}

    assert j1.pk in {j.pk for j in jednostki}  # U1 widoczny
    assert jednostka_drugiej_uczelni.uczelnia_id not in uczelnie  # U2 nie przecieka
