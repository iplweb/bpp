"""Faza 05b soft-delete: nagrobki dla konsumentów przyrostowych.

Nagrobek = rekord, który NALEŻY do tenanta, ale nie jest już wystawiany.
Dopełniamy ekspozycję, nigdy przynależność — dopełnienie przynależności
wystawiłoby w multi-hosted rekordy cudzych uczelni.
"""

import pytest

from cerif_export.oai.czasowniki import rejestr_providerow


def test_kazdy_provider_deklaruje_przynaleznosc():
    """Kontrakt musi być kompletny, inaczej nagrobki milkną w losowym secie.

    Provider bez ``przynaleznosc`` wywaliłby się dopiero przy harveście
    akurat tego setu — czyli u konsumenta, nie w testach.
    """
    for set_spec, provider in rejestr_providerow().items():
        assert hasattr(provider, "przynaleznosc"), (
            f"Provider setu {set_spec} nie deklaruje przynaleznosc()"
        )


@pytest.fixture
def druga_uczelnia(db):
    """Druga uczelnia z własną jednostką — multi-hosted."""
    from django.contrib.sites.models import Site

    from bpp.models import Jednostka, Uczelnia

    site = Site.objects.create(domain="druga.example.org", name="druga")
    uczelnia = Uczelnia.objects.create(nazwa="Druga", skrot="DRU", site=site)
    Jednostka.objects.create(nazwa="Jednostka Drugiej", skrot="JDR", uczelnia=uczelnia)
    return uczelnia


@pytest.mark.django_db
def test_nagrobki_nie_wyciekaja_miedzy_uczelniami(uczelnia, druga_uczelnia):
    """Dopełnienie NIE może objąć rekordów cudzego tenanta.

    To jedyne ryzyko, które dopełnienie widoczności wnosi wprost:
    ``widoczne_jednostki()`` filtruje ``uczelnia=uczelnia``, więc naiwne
    „wszystko minus widoczne" zamieniłoby każdą jednostkę drugiej uczelni
    w nagrobek pierwszej — wyciek identyfikatorów i lawina szumu.
    """
    from bpp.models import Jednostka
    from cerif_export import const

    provider = rejestr_providerow()[const.SET_ORGUNITS]
    nagrobki = provider.nagrobki(uczelnia, Jednostka)

    obce = Jednostka.objects.filter(uczelnia=druga_uczelnia)
    assert obce.exists(), "fixture musi utworzyć jednostkę drugiej uczelni"
    assert not nagrobki.filter(pk__in=obce.values("pk")).exists(), (
        "nagrobki uczelni A zawierają jednostkę uczelni B — wyciek tenanta"
    )
