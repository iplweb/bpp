from http.server import HTTPServer
from uuid import uuid4

import pytest
from model_mommy import mommy

from pbn_api.client import PBN_GET_LANGUAGES_URL, PBNClient
from pbn_api.models import Institution, Language, Publication, Scientist
from pbn_api.tests.utils import MockTransport

from bpp.models import Charakter_Formalny, Jezyk, Uczelnia, Wydawnictwo_Ciagle, const
from bpp.models.const import RODZAJ_PBN_KSIAZKA

MOCK_RETURNED_MONGODB_DATA = dict(
    status="foo",
    verificationLevel="bar",
    verified=True,
    versions=[{"current": True, "baz": "quux"}],
    mongoId="123",
)


@pytest.fixture
def pbn_client():
    transport = MockTransport()
    return PBNClient(transport=transport)


@pytest.fixture
def pbn_language():
    return Language.objects.create(code="pl", language={"lol": "XD"})


def _zrob_autora_pbn(autor):
    autor.pbn_uid = mommy.make(Scientist)
    autor.save()
    return autor


@pytest.fixture
def pbn_autor(autor_jan_nowak):
    return _zrob_autora_pbn(autor_jan_nowak)


@pytest.fixture
def pbn_jednostka(jednostka):
    jednostka.pbn_uid = mommy.make(Institution)
    jednostka.save()
    return jednostka


@pytest.fixture
def pbn_jezyk(jezyki, pbn_language):
    polski = Jezyk.objects.get(nazwa="polski")
    polski.pbn_uid = pbn_language
    polski.save()
    return polski


def _zrob_wydawnictwo_pbn(
    wydawnictwo_ciagle, jezyk, rodzaj_pbn=const.RODZAJ_PBN_ARTYKUL
):
    cf = wydawnictwo_ciagle.charakter_formalny
    cf.rodzaj_pbn = rodzaj_pbn
    cf.save()

    wydawnictwo_ciagle.jezyk = jezyk

    wydawnictwo_ciagle.doi = "123;.123/doi"
    wydawnictwo_ciagle.save()


@pytest.fixture
def pbn_wydawnictwo_ciagle(wydawnictwo_ciagle, pbn_jezyk) -> Wydawnictwo_Ciagle:
    _zrob_wydawnictwo_pbn(wydawnictwo_ciagle, pbn_jezyk)
    return wydawnictwo_ciagle


@pytest.fixture
def pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina(
    pbn_wydawnictwo_ciagle, autor_z_dyscyplina, pbn_jednostka
) -> Wydawnictwo_Ciagle:
    _zrob_autora_pbn(autor_z_dyscyplina.autor)
    pbn_wydawnictwo_ciagle.dodaj_autora(
        autor_z_dyscyplina.autor,
        pbn_jednostka,
        dyscyplina_naukowa=autor_z_dyscyplina.dyscyplina_naukowa,
    )
    return pbn_wydawnictwo_ciagle


@pytest.fixture
def pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina(
    pbn_wydawnictwo_zwarte, autor_z_dyscyplina, pbn_jednostka
) -> Wydawnictwo_Ciagle:
    _zrob_autora_pbn(autor_z_dyscyplina.autor)
    pbn_wydawnictwo_zwarte.dodaj_autora(
        autor_z_dyscyplina.autor,
        pbn_jednostka,
        dyscyplina_naukowa=autor_z_dyscyplina.dyscyplina_naukowa,
    )
    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_rozdzial_z_autorem_z_dyscyplina(
    pbn_wydawnictwo_zwarte, autor_z_dyscyplina, pbn_jednostka
) -> Wydawnictwo_Ciagle:
    _zrob_autora_pbn(autor_z_dyscyplina.autor)
    pbn_wydawnictwo_zwarte.dodaj_autora(
        autor_z_dyscyplina.autor,
        pbn_jednostka,
        dyscyplina_naukowa=autor_z_dyscyplina.dyscyplina_naukowa,
    )
    cf = pbn_wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    cf.save()
    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_charakter_formalny() -> Charakter_Formalny:
    return mommy.make(Charakter_Formalny, rodzaj_pbn=RODZAJ_PBN_KSIAZKA)


@pytest.fixture
def pbn_wydawnictwo_zwarte(wydawnictwo_zwarte, pbn_jezyk):
    cf = wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    wydawnictwo_zwarte.jezyk = pbn_jezyk

    wydawnictwo_zwarte.doi = "123;.123/doi"
    wydawnictwo_zwarte.save()

    return wydawnictwo_zwarte


@pytest.fixture
def pbn_wydawnictwo_zwarte_ksiazka(pbn_wydawnictwo_zwarte):
    cf = pbn_wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    cf.save()

    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_wydawnictwo_zwarte_rozdzial(pbn_wydawnictwo_zwarte):
    cf = pbn_wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    cf.save()

    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_publication(db):
    return Publication.objects.create(mongoId=123, versions={})


@pytest.fixture
def pbn_wydawnictwo_zwarte_z_charakterem(
    pbn_wydawnictwo_zwarte, pbn_charakter_formalny
):
    pbn_wydawnictwo_zwarte.charakter_formalny = pbn_charakter_formalny
    pbn_wydawnictwo_zwarte.save()
    return pbn_wydawnictwo_zwarte


@pytest.fixture
def pbn_uczelnia(pbn_client) -> Uczelnia:
    uczelnia = mommy.make(
        Uczelnia,
    )

    uczelnia.pbn_client = lambda *args, **kw: pbn_client
    pbn_client.transport.return_values[PBN_GET_LANGUAGES_URL] = {"1": "23"}

    uczelnia.pbn_integracja = True
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.pbn_app_name = "FOO"
    uczelnia.pbn_app_token = "BAR"
    uczelnia.pbn_api_root = "https://localhost/pbn/mockapi/v1/"
    uczelnia.save()

    return uczelnia


@pytest.fixture
def pbn_serwer(pbn_uczelnia, httpserver: HTTPServer):
    pbn_uczelnia.pbn_api_root = httpserver.url_for("/")
    pbn_uczelnia.save()
    return httpserver


def pbn_publication_json(
    year,
    title="tytul pracy",
    mongoId=None,
    isbn=None,
    status="ACTIVE",
    verified=True,
    doi=None,
):
    obj = {"title": title, "year": year}
    if isbn:
        obj.update({"isbn": isbn})
    if doi:
        obj.update({"doi": doi})

    return {
        "mongoId": mongoId or str(uuid4()),
        "status": status,
        "verificationLevel": "MODERATOR",
        "verified": verified,
        "versions": [{"current": True, "object": obj}],
    }


def pbn_pageable_json(content):
    return {
        "content": content,
        "first": True,
        "last": True,
        "number": 0,
        "numberofElements": len(content),
        "pageable": {
            "offset": 0,
            "pageNumber": 0,
            "pageSize": len(content),
            "paged": True,
            "sort": {"sorted": False, "unsorted": True},
            "unpaged": False,
        },
        "size": len(content),
        "sort": {"sorted": False, "unsorted": True},
        "totalElements": len(content),
        "totalPages": 1,
    }
