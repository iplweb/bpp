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


@pytest.mark.django_db
def test_konferencja_bez_widocznych_publikacji_to_nagrobek(
    uczelnia, jednostka, typ_autor
):
    """Provider pochodny: konferencja znika, gdy znikną jej publikacje.

    Widoczność konferencji jest wyprowadzona z publikacji. Gdy jedyna
    publikacja wskazująca konferencję przestaje być widoczna, konferencja
    też wypada z feedu — i musi dostać nagrobek, a nie zniknąć po cichu.
    """
    from model_bakery import baker

    from bpp.models import Konferencja, Wydawnictwo_Ciagle
    from cerif_export import const

    konferencja = baker.make(Konferencja)
    praca = baker.make(Wydawnictwo_Ciagle, konferencja=konferencja)
    # Nazwisko/imiona jawnie: baker generuje 500-znakowe losowe łańcuchy,
    # a ``dodaj_autora`` skleja z nich ``zapisany_jako`` (max 512 znaków).
    praca.dodaj_autora(
        baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan"), jednostka
    )

    provider = rejestr_providerow()[const.SET_EVENTS]
    assert (
        not provider.nagrobki(uczelnia, Konferencja).filter(pk=konferencja.pk).exists()
    ), "konferencja z widoczną publikacją nie jest nagrobkiem"

    praca.nie_eksportuj_przez_api = True
    praca.save()

    assert (
        provider.nagrobki(uczelnia, Konferencja).filter(pk=konferencja.pk).exists()
    ), (
        "konferencja straciła jedyną widoczną publikację, a nie dostała "
        "nagrobka — znika z feedu po cichu"
    )
