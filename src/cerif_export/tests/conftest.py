"""Wspólne fixtury dla testów eksportu CERIF.

``test_providery.py`` ma własne, historyczne kopie części z nich — te tutaj
są dla modułów pisanych później i celowo nie ruszają tamtych, żeby nie
przepisywać przechodzącej suity.
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Jednostka,
    Status_Korekty,
    Typ_Odpowiedzialnosci,
    Uczelnia,
)


@pytest.fixture
def uczelnia(db):
    site = Site.objects.create(domain="cerif.example.org", name="cerif.example.org")
    return Uczelnia.objects.create(
        nazwa="Uczelnia CERIF",
        skrot="UCE",
        site=site,
        ror_id="https://ror.org/016f61126",
    )


@pytest.fixture
def jednostka(uczelnia):
    return Jednostka.objects.create(
        nazwa="Jednostka CERIF", skrot="JCE", uczelnia=uczelnia
    )


@pytest.fixture
def typ_autor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )[0]


@pytest.fixture
def status_ok(db):
    return Status_Korekty.objects.get_or_create(nazwa="po korekcie")[0]


@pytest.fixture
def fabryka_autorow(jednostka, typ_autor):
    """Autor powiązany z jednostką uczelni — czyli kandydat do eksportu.

    Samo ``pokazuj=True`` nie wystarcza: reguła widoczności wymaga też
    powiązania ``Autor_Jednostka`` z jednostką TEJ uczelni, inaczej każdy
    tenant eksportowałby cudzych autorów.

    Zależność od ``typ_autor`` jest celowa, mimo że sam ``Autor`` jej nie
    potrzebuje: każdy konsument tej fabryki podpina autora do rekordu przez
    ``dodaj_autora()``, a to robi ``Typ_Odpowiedzialnosci.objects.get(
    skrot="aut.")``. Wiersz ten pochodzi z baseline'u, więc *zwykle* jest
    w bazie — ale test transakcyjny truncate'uje tabele i kolejne testy
    tego samego workera zastają je puste. Test, który liczy na dane
    referencyjne zamiast je stworzyć, jest wtedy zielony albo czerwony
    zależnie od tego, co się przed nim wykonało.
    """

    def zbuduj(nazwisko="Kowalski", pokazuj=True, powiaz=True, **kwargs):
        autor = baker.make(
            Autor, nazwisko=nazwisko, imiona="Jan", pokazuj=pokazuj, **kwargs
        )
        if powiaz:
            Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
        return autor

    return zbuduj


@pytest.fixture
def fabryka_wydawnictw(jednostka, typ_autor, status_ok):
    """Widoczne wydawnictwo z jednym autorstwem."""

    def zbuduj(model, autor=None, **kwargs):
        kwargs.setdefault("status_korekty", status_ok)
        kwargs.setdefault("nie_eksportuj_przez_api", False)
        kwargs.setdefault("rok", 2020)
        rekord = baker.make(model, **kwargs)
        if autor is not None:
            rekord.dodaj_autora(autor, jednostka)
        return rekord

    return zbuduj
