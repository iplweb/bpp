"""FD#512: importer publikacji łączy źródła danych.

Import zaczęty od DOI (CrossRef) sam sprawdza, czy praca jest w PBN — po
DOI, a książkę także po ISBN — i dociąga stamtąd odpowiednik w PBN,
identyfikatory osób i brakujące pola. Import zaczęty od PBN sprawdza
CrossRef po DOI. Dyscypliny przychodzą z oświadczeń w profilu instytucji.
Redaktor widzi w kreatorze, skąd pochodzi która informacja.

Wszystko bez sieci: odpowiedzi PBN i CrossRef są podstawiane.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.db import transaction
from django.urls import reverse
from model_bakery import baker

from bpp import const
from bpp.models import Autor, Autor_Dyscyplina, Wydawnictwo_Zwarte
from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.providers import FetchedPublication
from importer_publikacji.tasks import fetch_session_task
from importer_publikacji.views.pbn_check import _link_pbn_uid
from importer_publikacji.views.pbn_search import _search_pbn_equivalents
from importer_publikacji.zrodla import (
    DOMYSLNY_TIMEOUT_DRUGIEGO_ZRODLA,
    KLUCZ_ZRODEL,
    STAN_BRAK,
    STAN_NIE_SPRAWDZONO,
    STAN_NIEJEDNOZNACZNE,
    STAN_ZNALEZIONO,
    ZRODLO_CROSSREF,
    ZRODLO_PBN,
    ZRODLO_PROFIL,
    dolacz_profil_instytucji,
    jedna_szybka_proba,
    polacz_zrodla,
    uwagi_o_dyscyplinach,
    uzupelnij_autorow,
    uzupelnij_brakujace_pola,
    zastosuj_dyscypliny_z_profilu,
)
from importer_publikacji.zrodla import (
    _pobierz_z_crossref as _prawdziwe_pobierz_z_crossref,
)
from pbn_api.exceptions import HttpException
from pbn_api.models import Institution, OswiadczenieInstytucji, Publication, Scientist

PRACA_PBN = "5e709189878c28a04737dc6f"
KSIAZKA_PBN = "5e709189878c28a04737dc70"
OSOBA_1 = "5e709189878c28a04737dc61"
OSOBA_2 = "5e709189878c28a04737dc62"
DOI = "10.1234/fd512.2024.001"
ORCID_1 = "0000-0002-1825-0097"
ISBN = "978-83-01-00000-1"


def _praca_pbn(mongo_id=PRACA_PBN, **obiekt):
    dane = {
        "title": "Łączenie źródeł w praktyce",
        "doi": DOI,
        "year": 2024,
        "type": "ARTICLE",
        "authors": {
            OSOBA_1: {"lastName": "Kowalski", "name": "Jan"},
            OSOBA_2: {"lastName": "Nowak", "name": "Anna"},
        },
        "abstracts": {"pl": "Streszczenie z PBN."},
        "openAccess": {"license": "CC_BY"},
    }
    dane.update(obiekt)
    return {
        "mongoId": mongo_id,
        "status": "ACTIVE",
        "verificationLevel": "VERIFIED",
        "verified": True,
        "versions": [{"current": True, "object": dane}],
    }


def _z_crossref(**kw):
    dane = {
        "raw_data": {"DOI": DOI, "type": "journal-article"},
        "title": "Łączenie źródeł w praktyce",
        "doi": DOI,
        "year": 2024,
        "publication_type": "journal-article",
        "authors": [
            {"family": "Kowalski", "given": "Jan", "orcid": ORCID_1},
            {"family": "Nowak", "given": "A.", "orcid": ""},
        ],
        "source_title": "Czasopismo Testowe",
        "volume": "7",
    }
    dane.update(kw)
    return FetchedPublication(**dane)


def _osoba(pk, nazwisko, imiona):
    return baker.make(
        Scientist,
        mongoId=pk,
        versions=[{"current": True, "object": {"lastName": nazwisko, "name": imiona}}],
    )


def _sesja(user, provider="CrossRef", **kw):
    dane = {
        "created_by": user,
        "provider_name": provider,
        "identifier": DOI,
        "raw_data": {},
        "normalized_data": {},
        "status": ImportSession.Status.FETCHING,
    }
    dane.update(kw)
    return ImportSession.objects.create(**dane)


def _klient_pbn(po_doi=None, po_isbn=(), po_id=None):
    """Atrapa klienta PBN: odpowiedź na DOI, wyniki szukania po ISBN, po id."""
    client = MagicMock()
    if po_doi is None:
        client.get_publication_by_doi.side_effect = HttpException(
            404, "/api/v1/publications/doi/", "Not found"
        )
    elif isinstance(po_doi, Exception):
        client.get_publication_by_doi.side_effect = po_doi
    else:
        client.get_publication_by_doi.return_value = po_doi
    client.search_publications.side_effect = lambda **kw: iter(list(po_isbn))
    client.get_publication_by_id.side_effect = lambda mongo_id: (po_id or {})[mongo_id]
    return client


def _pobierz(sesja, wynik_dostawcy, client=None):
    """Uruchom zadanie pobierania z podstawionym dostawcą i klientem PBN."""
    dostawca = MagicMock()
    dostawca.fetch.return_value = wynik_dostawcy
    klient = (
        patch("importer_publikacji.providers.pbn._get_pbn_client", return_value=client)
        if client is not None
        else patch(
            "importer_publikacji.providers.pbn._get_pbn_client",
            side_effect=ValueError("Brak konfiguracji PBN"),
        )
    )
    with (
        patch("importer_publikacji.tasks.get_provider", return_value=dostawca),
        klient,
        # Dociąganie danych osób to osobne zapytania do PBN (FD#510).
        patch(
            "importer_publikacji.providers.pbn.pobierz_brakujace_osoby", return_value=0
        ),
    ):
        fetch_session_task.apply(args=[sesja.pk, sesja.created_by_id]).get()
    sesja.refresh_from_db()
    return sesja


def _wpis(sesja, zrodlo):
    return next(w for w in sesja.normalized_data[KLUCZ_ZRODEL] if w["zrodlo"] == zrodlo)


# --- Uzupełnianie pól i autorów (bez bazy) ------------------------------------


def test_uzupelnia_tylko_brakujace_pola():
    glowne = _z_crossref(abstract=None, license_url=None)
    dodatkowe = _z_crossref(
        title="Inny tytuł",
        volume="99",
        abstract="Streszczenie z PBN.",
        license_url="https://creativecommons.org/licenses/by/4.0/",
    )

    uzupelnione = uzupelnij_brakujace_pola(glowne, dodatkowe)

    assert uzupelnione == ["streszczenie", "licencja"]
    assert glowne.abstract == "Streszczenie z PBN."
    # Strażnik: dane źródła wybranego przez redaktora nie są nadpisywane.
    assert glowne.title == "Łączenie źródeł w praktyce"
    assert glowne.volume == "7"


@pytest.mark.django_db
def test_jezyk_spoza_slownika_nie_blokuje_wykrywania(jezyki):
    """PBN podaje ``pol``, którego słownik języków BPP nie zna — nie
    przenosimy go, żeby zadziałało wykrywanie języka z tytułu."""
    glowne = _z_crossref(language=None)

    uzupelnij_brakujace_pola(glowne, _z_crossref(language="pol"))
    assert glowne.language is None

    assert uzupelnij_brakujace_pola(glowne, _z_crossref(language="pl")) == ["język"]
    assert glowne.language == "pl"


def test_autorzy_dostaja_identyfikatory_pbn_i_orcid():
    glowne = _z_crossref()
    dodatkowe = _z_crossref(
        authors=[
            {"family": "Kowalski", "given": "Jan", "orcid": "", "pbn_uid": OSOBA_1},
            {"family": "Nowak", "given": "Anna", "orcid": "0000-0001-0000-0002"},
        ]
    )
    dodatkowe.authors[1]["pbn_uid"] = OSOBA_2

    wynik = uzupelnij_autorow(glowne, dodatkowe)

    assert wynik == {"pbn_uid": 2, "orcid": 1, "dodani": 0}
    kowalski, nowak = glowne.authors
    assert kowalski["pbn_uid"] == OSOBA_1
    # ORCID ze źródła głównego zostaje.
    assert kowalski["orcid"] == ORCID_1
    # „A.” ↔ „Anna”: dopasowanie po nazwisku i inicjale, bo jest jednoznaczne.
    assert nowak["pbn_uid"] == OSOBA_2
    assert nowak["orcid"] == "0000-0001-0000-0002"
    # Zapis nazwisk i kolejność — jak w źródle głównym.
    assert nowak["given"] == "A."


def test_autorzy_niejednoznaczni_nie_dostaja_cudzego_identyfikatora():
    glowne = _z_crossref(
        authors=[
            {"family": "Kowalski", "given": "J.", "orcid": ""},
            {"family": "Nowak", "given": "A.", "orcid": ""},
        ]
    )
    dodatkowe = _z_crossref(
        authors=[
            {"family": "Kowalski", "given": "Jan", "pbn_uid": OSOBA_1},
            {"family": "Kowalski", "given": "Jerzy", "pbn_uid": OSOBA_2},
        ]
    )

    wynik = uzupelnij_autorow(glowne, dodatkowe)

    assert wynik == {"pbn_uid": 0, "orcid": 0, "dodani": 0}
    assert "pbn_uid" not in glowne.authors[0]


def test_ta_sama_osoba_jako_redaktor_i_autor():
    """PBN podaje tę samą osobę dwa razy (redaktor i autor) — to nie jest
    niejednoznaczność."""
    glowne = _z_crossref(authors=[{"family": "Kowalski", "given": "Jan"}])
    osoba = {"family": "Kowalski", "given": "Jan", "pbn_uid": OSOBA_1}
    dodatkowe = _z_crossref(
        authors=[{**osoba, "typ_ogolny": const.TO_REDAKTOR}, dict(osoba)]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["pbn_uid"] == 1
    assert glowne.authors[0]["pbn_uid"] == OSOBA_1


def test_brak_autorow_w_zrodle_glownym_bierze_liste_z_drugiego():
    glowne = _z_crossref(authors=[])
    dodatkowe = _z_crossref(
        authors=[{"family": "Kowalski", "given": "Jan", "pbn_uid": OSOBA_1}]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["dodani"] == 1
    assert glowne.authors == dodatkowe.authors


# --- Start od DOI: sprawdzenie w PBN ------------------------------------------


@pytest.mark.django_db
def test_import_z_crossref_dociaga_dane_z_pbn(importer_user):
    """Praca z CrossRef jest w PBN: odpowiednik, identyfikatory osób
    i brakujące pola przychodzą z PBN zaraz po pobraniu danych."""
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan")
    # Autor BPP zapisany inaczej niż w CrossRef — rozpozna go dopiero
    # identyfikator osoby w PBN.
    autor = baker.make(Autor, nazwisko="Kowalski-Zamężny", imiona="J", pbn_uid=osoba)

    sesja = _pobierz(
        _sesja(importer_user), _z_crossref(), _klient_pbn(po_doi=_praca_pbn())
    )

    assert sesja.status == ImportSession.Status.FETCHED
    assert sesja.matched_data["pbn_mongo_id"] == PRACA_PBN
    assert Publication.objects.filter(pk=PRACA_PBN).exists()

    wpis = _wpis(sesja, ZRODLO_PBN)
    assert wpis["stan"] == STAN_ZNALEZIONO
    assert wpis["po"] == "DOI"
    assert wpis["pola"] == ["streszczenie", "licencja"]
    assert wpis["autorzy"] == {"pbn_uid": 2, "orcid": 0, "dodani": 0}

    nd = sesja.normalized_data
    assert nd["abstract"] == "Streszczenie z PBN."
    assert nd["abstracts"] == [{"text": "Streszczenie z PBN.", "language": None}]
    # Strażnik: pola z CrossRef zostają.
    assert nd["volume"] == "7"
    assert nd["source_title"] == "Czasopismo Testowe"

    kowalski = sesja.authors.get(order=0)
    assert kowalski.pbn_uid == OSOBA_1
    assert kowalski.matched_autor == autor
    assert kowalski.match_status == ImportedAuthor.MatchStatus.AUTO_EXACT
    assert sesja.authors.get(order=1).pbn_uid == OSOBA_2


@pytest.mark.django_db
def test_pracy_nie_ma_w_pbn_import_bez_zmian(importer_user):
    """Strażnik: gdy PBN nie zna pracy, dane są dokładnie takie, jak
    podał dostawca."""
    sesja = _pobierz(_sesja(importer_user), _z_crossref(), _klient_pbn())

    assert sesja.status == ImportSession.Status.FETCHED
    assert "pbn_mongo_id" not in sesja.matched_data
    assert _wpis(sesja, ZRODLO_PBN) == {"zrodlo": ZRODLO_PBN, "stan": STAN_BRAK}
    assert sesja.normalized_data["abstract"] is None
    assert sesja.authors.get(order=0).pbn_uid == ""


@pytest.mark.django_db
def test_blad_pbn_nie_przerywa_importu(importer_user):
    blad = HttpException(500, "/api/v1/publications/doi/", "Internal error")

    sesja = _pobierz(_sesja(importer_user), _z_crossref(), _klient_pbn(po_doi=blad))

    assert sesja.status == ImportSession.Status.FETCHED
    wpis = _wpis(sesja, ZRODLO_PBN)
    assert wpis["stan"] == STAN_NIE_SPRAWDZONO
    assert "PBN" in wpis["komunikat"]
    assert "pbn_mongo_id" not in sesja.matched_data


@pytest.mark.django_db
def test_nieoczekiwany_blad_laczenia_nie_przerywa_importu(importer_user):
    with patch(
        "importer_publikacji.zrodla._dolacz_pbn", side_effect=RuntimeError("bum")
    ):
        sesja = _pobierz(_sesja(importer_user), _z_crossref())

    assert sesja.status == ImportSession.Status.FETCHED
    assert _wpis(sesja, ZRODLO_PBN)["stan"] == STAN_NIE_SPRAWDZONO
    assert sesja.normalized_data["title"] == "Łączenie źródeł w praktyce"


@pytest.mark.django_db
def test_bez_konfiguracji_pbn_import_dziala(importer_user):
    sesja = _pobierz(_sesja(importer_user), _z_crossref())

    assert sesja.status == ImportSession.Status.FETCHED
    wpis = _wpis(sesja, ZRODLO_PBN)
    assert wpis["stan"] == STAN_NIE_SPRAWDZONO
    assert wpis["komunikat"] == "Dostęp do PBN nie jest skonfigurowany."


@pytest.mark.django_db
def test_patent_nie_jest_sprawdzany_w_pbn(importer_user):
    client = _klient_pbn(po_doi=_praca_pbn())

    sesja = _pobierz(
        _sesja(importer_user, provider="BibTeX"),
        _z_crossref(publication_type="patent"),
        client,
    )

    assert sesja.normalized_data[KLUCZ_ZRODEL] == []
    client.get_publication_by_doi.assert_not_called()
    assert "pbn_mongo_id" not in sesja.matched_data


# --- Książka: szukanie w PBN po ISBN ------------------------------------------


def _ksiazka(**kw):
    dane = {
        "title": "Monografia testowa",
        "publication_type": "book",
        "isbn": ISBN,
        "source_title": None,
        "volume": None,
    }
    dane.update(kw)
    return _z_crossref(**dane)


def _ksiazka_pbn(tytul="Monografia testowa. Podtytuł", mongo_id=KSIAZKA_PBN):
    return _praca_pbn(
        mongo_id, title=tytul, type="BOOK", doi=None, isbn="9788301000001"
    )


@pytest.mark.django_db
def test_ksiazka_bez_doi_w_pbn_znajdowana_po_isbn(importer_user):
    client = _klient_pbn(
        po_isbn=[{"mongoId": KSIAZKA_PBN}], po_id={KSIAZKA_PBN: _ksiazka_pbn()}
    )

    sesja = _pobierz(_sesja(importer_user), _ksiazka(), client)

    wpis = _wpis(sesja, ZRODLO_PBN)
    assert wpis["stan"] == STAN_ZNALEZIONO
    assert wpis["po"] == "ISBN"
    assert sesja.matched_data["pbn_mongo_id"] == KSIAZKA_PBN
    # PBN nie normalizuje zapytania — ISBN idzie bez myślników.
    zapytania = [c.kwargs["isbn"] for c in client.search_publications.call_args_list]
    assert "9788301000001" in zapytania
    assert ISBN not in zapytania


@pytest.mark.django_db
def test_ksiazka_o_innym_tytule_nie_jest_wiazana_automatycznie(importer_user):
    client = _klient_pbn(
        po_isbn=[{"mongoId": KSIAZKA_PBN}],
        po_id={KSIAZKA_PBN: _ksiazka_pbn(tytul="Zupełnie inna książka")},
    )

    sesja = _pobierz(_sesja(importer_user), _ksiazka(), client)

    wpis = _wpis(sesja, ZRODLO_PBN)
    assert wpis["stan"] == STAN_NIEJEDNOZNACZNE
    assert "Zupełnie inna książka" in wpis["komunikat"]
    assert "pbn_mongo_id" not in sesja.matched_data
    assert sesja.authors.get(order=0).pbn_uid == ""


@pytest.mark.django_db
def test_kilka_ksiazek_o_tym_samym_isbn_wymaga_wyboru(importer_user):
    client = _klient_pbn(po_isbn=[{"mongoId": KSIAZKA_PBN}, {"mongoId": PRACA_PBN}])

    sesja = _pobierz(_sesja(importer_user), _ksiazka(), client)

    assert _wpis(sesja, ZRODLO_PBN)["stan"] == STAN_NIEJEDNOZNACZNE
    assert "pbn_mongo_id" not in sesja.matched_data
    client.get_publication_by_id.assert_not_called()


@pytest.mark.django_db
def test_artykul_nie_jest_szukany_po_isbn(importer_user):
    """Strażnik: ISBN przy rozdziale lub artykule to ISBN tomu, nie pracy."""
    client = _klient_pbn(po_isbn=[{"mongoId": KSIAZKA_PBN}])

    sesja = _pobierz(
        _sesja(importer_user),
        _z_crossref(isbn=ISBN, publication_type="book-chapter"),
        client,
    )

    assert _wpis(sesja, ZRODLO_PBN)["stan"] == STAN_BRAK
    client.search_publications.assert_not_called()


def test_krok_sprawdz_w_pbn_szuka_tez_po_isbn():
    client = MagicMock()
    client.search_publications.side_effect = lambda **kw: iter(
        [{"mongoId": KSIAZKA_PBN, "title": "Monografia testowa"}]
        if "isbn" in kw
        else []
    )
    uczelnia = MagicMock(pbn_api_root="https://pbn.example")
    uczelnia.pbn_client.return_value = client
    sesja = SimpleNamespace(
        uczelnia=uczelnia,
        normalized_data={"title": "Monografia testowa", "isbn": ISBN},
    )

    with patch("importer_publikacji.views.pbn_search._search_pbn_local_www") as www:
        www.return_value = []
        wynik = _search_pbn_equivalents(sesja, MagicMock(pbn_token="t"))

    assert [r["mongo_id"] for r in wynik["by_isbn"]] == [KSIAZKA_PBN]
    assert wynik["by_isbn"][0]["axis"] == "ISBN"
    assert wynik["total_unique"] == 1


# --- Start od PBN: sprawdzenie w CrossRef -------------------------------------


def _z_pbn():
    from importer_publikacji.providers.pbn import publikacja_z_danych_pbn

    return publikacja_z_danych_pbn(_praca_pbn(abstracts={}, openAccess=None), PRACA_PBN)


@pytest.fixture
def crossref(monkeypatch):
    """Podstaw odpowiedź CrossRef (``None`` = CrossRef nie zna DOI)."""
    from importer_publikacji.providers import crossref as crossref_mod

    def _ustaw(dane):
        monkeypatch.setattr(
            crossref_mod.CrossrefAPICache,
            "objects",
            SimpleNamespace(get_by_doi=lambda doi: dane),
        )
        # Fikstura z conftest odcina CrossRef w całości — tu przywracamy
        # prawdziwego dostawcę, tylko z podstawioną odpowiedzią.
        monkeypatch.setattr(
            "importer_publikacji.zrodla._pobierz_z_crossref",
            lambda doi: crossref_mod.CrossRefProvider().fetch(doi),
        )

    return _ustaw


@pytest.mark.django_db
def test_import_z_pbn_dociaga_dane_z_crossref(importer_user, crossref):
    crossref(
        {
            "DOI": DOI,
            "type": "journal-article",
            "title": ["Tytuł z CrossRef"],
            "author": [
                {
                    "family": "Kowalski",
                    "given": "Jan",
                    "ORCID": f"https://orcid.org/{ORCID_1}",
                }
            ],
            "container-title": ["Czasopismo Testowe"],
            "abstract": "Streszczenie z CrossRef.",
            "page": "10-20",
            "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
            "published": {"date-parts": [[2024]]},
        }
    )

    sesja = _pobierz(_sesja(importer_user, provider="PBN"), _z_pbn())

    assert sesja.status == ImportSession.Status.FETCHED
    wpis = _wpis(sesja, ZRODLO_CROSSREF)
    assert wpis["stan"] == STAN_ZNALEZIONO
    assert wpis["pola"] == [
        "tytuł źródła",
        "streszczenie",
        "strony",
        "licencja",
    ]
    assert wpis["autorzy"] == {"pbn_uid": 0, "orcid": 1, "dodani": 0}

    nd = sesja.normalized_data
    assert nd["abstract"] == "Streszczenie z CrossRef."
    assert nd["pages"] == "10-20"
    # Strażnik: tytuł i lista autorów zostają z PBN.
    assert nd["title"] == "Łączenie źródeł w praktyce"
    assert [a["family"] for a in nd["authors"]] == ["Kowalski", "Nowak"]

    kowalski = sesja.authors.get(order=0)
    assert kowalski.orcid == ORCID_1
    assert kowalski.pbn_uid == OSOBA_1
    # Praca pobrana z PBN ma odpowiednik w PBN — rekord zostanie powiązany.
    assert sesja.matched_data["pbn_mongo_id"] == PRACA_PBN


@pytest.mark.django_db
def test_import_z_pbn_gdy_crossref_nie_zna_doi(importer_user, crossref):
    crossref(None)

    sesja = _pobierz(_sesja(importer_user, provider="PBN"), _z_pbn())

    assert sesja.status == ImportSession.Status.FETCHED
    assert _wpis(sesja, ZRODLO_CROSSREF) == {
        "zrodlo": ZRODLO_CROSSREF,
        "stan": STAN_BRAK,
    }
    assert sesja.normalized_data["abstract"] is None


def test_import_z_pbn_bez_doi_nie_pyta_crossref():
    sesja = SimpleNamespace(pk=1, provider_name="PBN", matched_data={}, uczelnia=None)
    wynik = _z_pbn()
    wynik.doi = None

    with patch("importer_publikacji.zrodla._pobierz_z_crossref") as pobierz:
        assert polacz_zrodla(sesja, wynik) == []

    pobierz.assert_not_called()
    assert sesja.matched_data == {"pbn_mongo_id": PRACA_PBN}


DANE_CROSSREF = {
    "DOI": DOI,
    "type": "journal-article",
    "title": ["Tytuł z CrossRef"],
    "author": [
        {"family": "Kowalski", "given": "Jan", "ORCID": f"https://orcid.org/{ORCID_1}"}
    ],
    "container-title": ["Czasopismo Testowe"],
    "page": "10-20",
    "published": {"date-parts": [[2024]]},
}


def _z_bibtex():
    """Ubogi wpis BibTeX: tytuł, DOI, autorzy — bez źródła, stron, ORCID."""
    return _z_crossref(
        raw_data={},
        source_title=None,
        volume=None,
        authors=[{"family": "Kowalski", "given": "Jan", "orcid": ""}],
    )


@pytest.mark.django_db
def test_import_z_bibtex_dociaga_dane_z_pbn_i_z_crossref(importer_user, crossref):
    """Start z BibTeX-a (tak samo DSpace i WWW) z numerem DOI: importer sam
    pyta i PBN, i CrossRef — bez zastępowania sesji danymi z CrossRef."""
    crossref(DANE_CROSSREF)

    sesja = _pobierz(
        _sesja(importer_user, provider="BibTeX"),
        _z_bibtex(),
        _klient_pbn(po_doi=_praca_pbn()),
    )

    assert [w["zrodlo"] for w in sesja.normalized_data[KLUCZ_ZRODEL]] == [
        ZRODLO_PBN,
        ZRODLO_CROSSREF,
        ZRODLO_PROFIL,
    ]
    assert _wpis(sesja, ZRODLO_PBN)["pola"] == ["streszczenie", "licencja"]
    z_crossref = _wpis(sesja, ZRODLO_CROSSREF)
    assert z_crossref["stan"] == STAN_ZNALEZIONO
    assert z_crossref["pola"] == ["tytuł źródła", "strony"]
    assert z_crossref["autorzy"] == {"pbn_uid": 0, "orcid": 1, "dodani": 0}

    nd = sesja.normalized_data
    assert nd["source_title"] == "Czasopismo Testowe"
    assert nd["abstract"] == "Streszczenie z PBN."
    # Strażnik: tytuł zostaje z BibTeX-a.
    assert nd["title"] == "Łączenie źródeł w praktyce"
    kowalski = sesja.authors.get(order=0)
    assert (kowalski.pbn_uid, kowalski.orcid) == (OSOBA_1, ORCID_1)
    assert sesja.matched_data["pbn_mongo_id"] == PRACA_PBN


@pytest.mark.django_db
def test_awaria_pbn_nie_blokuje_crossref(importer_user, crossref):
    crossref(DANE_CROSSREF)

    with patch(
        "importer_publikacji.zrodla._dolacz_pbn", side_effect=RuntimeError("bum")
    ):
        sesja = _pobierz(_sesja(importer_user, provider="BibTeX"), _z_bibtex())

    assert _wpis(sesja, ZRODLO_PBN)["stan"] == STAN_NIE_SPRAWDZONO
    assert _wpis(sesja, ZRODLO_CROSSREF)["stan"] == STAN_ZNALEZIONO
    assert sesja.normalized_data["pages"] == "10-20"


@pytest.mark.django_db
def test_import_z_crossref_nie_pyta_crossref_drugi_raz(importer_user):
    with patch("importer_publikacji.zrodla._pobierz_z_crossref") as pobierz:
        sesja = _pobierz(_sesja(importer_user), _z_crossref(), _klient_pbn())

    pobierz.assert_not_called()
    assert [w["zrodlo"] for w in sesja.normalized_data[KLUCZ_ZRODEL]] == [ZRODLO_PBN]


def _weryfikacja(importer_client, sesja):
    return importer_client.get(
        reverse("importer_publikacji:verify", kwargs={"session_id": sesja.pk})
    ).content.decode()


@pytest.mark.django_db
def test_przycisk_pobierz_z_crossref_znika_gdy_crossref_nie_zna_doi(
    importer_client, importer_user
):
    """Przycisk zastępujący sesję danymi z CrossRef zostaje (poprawia błędny
    tytuł lub listę autorów ze źródła głównego), ale nie wtedy, gdy CrossRef
    tej pracy nie ma."""
    dane = {"title": "Praca", "doi": DOI}
    znana = _sesja(
        importer_user,
        provider="BibTeX",
        status=ImportSession.Status.FETCHED,
        normalized_data={
            **dane,
            KLUCZ_ZRODEL: [{"zrodlo": ZRODLO_CROSSREF, "stan": STAN_ZNALEZIONO}],
        },
    )
    nieznana = _sesja(
        importer_user,
        provider="BibTeX",
        status=ImportSession.Status.FETCHED,
        normalized_data={
            **dane,
            KLUCZ_ZRODEL: [{"zrodlo": ZRODLO_CROSSREF, "stan": STAN_BRAK}],
        },
    )

    assert "Pobierz z CrossRef" in _weryfikacja(importer_client, znana)
    tresc = _weryfikacja(importer_client, nieznana)
    assert "Pobierz z CrossRef" not in tresc
    assert "CrossRef nie zna numeru DOI tej pracy" in tresc


# --- Dyscypliny z oświadczeń w profilu instytucji -----------------------------


@pytest.fixture
def sesja_z_oswiadczeniem(importer_user, uczelnia, jednostka, dyscyplina1, dyscyplina2):
    """Sesja z jednym dopasowanym autorem uczelni i jego oświadczeniem
    (dyscyplina1) w lokalnej kopii profilu instytucji."""
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid=osoba)
    autor.dodaj_jednostke(jednostka)
    praca = baker.make(Publication, mongoId=PRACA_PBN, versions=[])
    baker.make(
        OswiadczenieInstytucji,
        publicationId=praca,
        personId=osoba,
        institutionId=baker.make(Institution),
        type="AUTHOR",
        inOrcid=False,
        disciplines={"name": dyscyplina1.nazwa},
    )
    sesja = _sesja(
        importer_user,
        uczelnia=uczelnia,
        normalized_data={"year": 2024},
        matched_data={"pbn_mongo_id": PRACA_PBN},
        status=ImportSession.Status.FETCHED,
    )
    wiersz = ImportedAuthor.objects.create(
        session=sesja,
        order=0,
        family_name="Kowalski",
        given_name="Jan",
        matched_autor=autor,
        matched_jednostka=jednostka,
        match_status=ImportedAuthor.MatchStatus.AUTO_EXACT,
    )
    return SimpleNamespace(
        sesja=sesja, wiersz=wiersz, autor=autor, d1=dyscyplina1, d2=dyscyplina2
    )


@pytest.mark.django_db
def test_dyscyplina_z_oswiadczenia_rozstrzyga_autora_dwudyscyplinowego(
    sesja_z_oswiadczeniem,
):
    """Autor ma na rok pracy dwie dyscypliny, więc importer sam nie wie,
    którą wybrać — rozstrzyga oświadczenie z profilu instytucji."""
    s = sesja_z_oswiadczeniem
    baker.make(
        Autor_Dyscyplina,
        autor=s.autor,
        rok=2024,
        dyscyplina_naukowa=s.d2,
        subdyscyplina_naukowa=s.d1,
    )

    wpis = dolacz_profil_instytucji(s.sesja, s.sesja.created_by)

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina == s.d1
    assert s.wiersz.dyscyplina_source == ImportedAuthor.DyscyplinaSource.PBN_PROFIL
    assert wpis["zrodlo"] == ZRODLO_PROFIL
    assert wpis["stan"] == STAN_ZNALEZIONO
    assert wpis["dyscypliny"] == 1
    # Redaktor bez tokenu PBN — oświadczenia z lokalnej kopii, bez sieci.
    assert wpis["oswiadczenia"] == "z lokalnej kopii danych PBN"


@pytest.mark.django_db
def test_oswiadczenie_niezgodne_z_przypisaniem_autora_jest_pomijane(
    sesja_z_oswiadczeniem,
):
    """Strażnik: dyscyplina, której autor nie ma na rok pracy, zablokowałaby
    utworzenie rekordu (FD#623) — nie podpowiadamy jej."""
    s = sesja_z_oswiadczeniem
    baker.make(Autor_Dyscyplina, autor=s.autor, rok=2024, dyscyplina_naukowa=s.d2)

    wpis = dolacz_profil_instytucji(s.sesja, s.sesja.created_by)

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina is None
    assert wpis["stan"] == STAN_BRAK
    assert wpis["pominiete"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zrodlo",
    [
        ImportedAuthor.DyscyplinaSource.MANUAL,
        ImportedAuthor.DyscyplinaSource.ZGLOSZENIE,
    ],
)
def test_oswiadczenie_nie_nadpisuje_wyboru_redaktora_ani_zgloszenia(
    sesja_z_oswiadczeniem, zrodlo
):
    s = sesja_z_oswiadczeniem
    s.wiersz.matched_dyscyplina = s.d2
    s.wiersz.dyscyplina_source = zrodlo
    s.wiersz.save()

    assert zastosuj_dyscypliny_z_profilu(s.sesja)["dyscypliny"] == 0

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina == s.d2
    assert s.wiersz.dyscyplina_source == zrodlo


@pytest.mark.django_db
def test_oswiadczenie_redaktora_nie_trafia_do_autora(sesja_z_oswiadczeniem):
    s = sesja_z_oswiadczeniem
    OswiadczenieInstytucji.objects.update(type="EDITOR")

    assert zastosuj_dyscypliny_z_profilu(s.sesja)["dyscypliny"] == 0


@pytest.mark.django_db
def test_redaktor_zalogowany_do_pbn_odswieza_oswiadczenia(sesja_z_oswiadczeniem):
    s = sesja_z_oswiadczeniem
    client = MagicMock()
    uzytkownik = MagicMock(pbn_token="token")
    uzytkownik.pbn_token_possibly_valid.return_value = True

    with patch.object(type(s.sesja.uczelnia), "pbn_client", return_value=client):
        wpis = dolacz_profil_instytucji(s.sesja, uzytkownik)

    pobranie = client.get_institution_statements_of_single_publication
    pobranie.assert_called_once_with(PRACA_PBN)
    assert wpis["oswiadczenia"] == "pobrane z PBN"
    # PBN nie podał żadnego oświadczenia — lokalna kopia jest podmieniona.
    assert wpis["dyscypliny"] == 0
    assert not OswiadczenieInstytucji.objects.filter(publicationId_id=PRACA_PBN)


@pytest.mark.django_db
def test_blad_pbn_przy_oswiadczeniach_zostawia_lokalna_kopie(sesja_z_oswiadczeniem):
    s = sesja_z_oswiadczeniem
    client = MagicMock()
    client.get_institution_statements_of_single_publication.side_effect = HttpException(
        403, "/api/v1/institutionProfile/", "Forbidden"
    )
    uzytkownik = MagicMock(pbn_token="token")
    uzytkownik.pbn_token_possibly_valid.return_value = True

    with patch.object(type(s.sesja.uczelnia), "pbn_client", return_value=client):
        wpis = dolacz_profil_instytucji(s.sesja, uzytkownik)

    assert wpis["oswiadczenia"] == "z lokalnej kopii danych PBN"
    assert wpis["dyscypliny"] == 1


def _autorzy(importer_client, sesja):
    return importer_client.get(
        reverse("importer_publikacji:authors", kwargs={"session_id": sesja.pk})
    ).content.decode()


@pytest.mark.django_db
def test_ostrzezenie_gdy_pbn_niezgodny_z_przypisaniem_na_rok(
    importer_client, sesja_z_oswiadczeniem
):
    """Oświadczenie w PBN mówi o dyscyplinie, której autor nie ma na rok
    pracy: nie zapisujemy jej (rekord by nie powstał), ale redaktor widzi
    ostrzeżenie — co jest w PBN, co w przypisaniu, co przyjęto."""
    s = sesja_z_oswiadczeniem
    baker.make(Autor_Dyscyplina, autor=s.autor, rok=2024, dyscyplina_naukowa=s.d2)
    s.wiersz.matched_dyscyplina = s.d2
    s.wiersz.dyscyplina_source = ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
    s.wiersz.save()

    dolacz_profil_instytucji(s.sesja, s.sesja.created_by)

    s.wiersz.refresh_from_db()
    # Strażnik: to, co trafi do rekordu, zostaje bez zmian.
    assert s.wiersz.matched_dyscyplina == s.d2
    assert s.wiersz.dyscyplina_source == ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
    uwaga = uwagi_o_dyscyplinach(s.sesja)[s.wiersz.pk]
    assert uwaga == {"pbn": s.d1, "przyjeta": s.d2, "rok": 2024, "na_rok": [s.d2]}

    tresc = _autorzy(importer_client, s.sesja)
    assert "uwaga-dyscyplina-pbn" in tresc
    assert f"oświadczenie w PBN:\n                        <strong>{s.d1}" in tresc
    assert f"na rok 2024:\n                        <strong>{s.d2}" in tresc
    assert f"Przyjęto: <strong>{s.d2}" in tresc


@pytest.mark.django_db
def test_informacja_gdy_pbn_rozni_sie_od_zgloszenia(
    importer_client, sesja_z_oswiadczeniem
):
    """PBN wygrywa z dyscypliną ze zgłoszenia publikacji, ale redaktor ma
    o różnicy wiedzieć."""
    from importer_publikacji.views.authors import _prefill_dyscypliny_z_zgloszen

    s = sesja_z_oswiadczeniem
    baker.make(
        Autor_Dyscyplina,
        autor=s.autor,
        rok=2024,
        dyscyplina_naukowa=s.d1,
        subdyscyplina_naukowa=s.d2,
    )
    zgloszenie = baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji",
        tytul_oryginalny="Łączenie źródeł w praktyce",
        rok=2024,
        status=0,
        rodzaj_zglaszanej_publikacji=1,
    )
    baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji_Autor",
        rekord=zgloszenie,
        autor=s.autor,
        jednostka=s.wiersz.matched_jednostka,
        dyscyplina_naukowa=s.d2,
        rok=2024,
    )
    s.sesja.zgloszenie = zgloszenie
    s.sesja.save()

    dolacz_profil_instytucji(s.sesja, s.sesja.created_by)
    _prefill_dyscypliny_z_zgloszen(s.sesja)

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina == s.d1
    assert s.wiersz.dyscyplina_source == ImportedAuthor.DyscyplinaSource.PBN_PROFIL
    uwaga = uwagi_o_dyscyplinach(s.sesja)[s.wiersz.pk]
    assert uwaga == {"pbn": s.d1, "przyjeta": s.d1, "rok": 2024, "zgloszenie": s.d2}

    tresc = _autorzy(importer_client, s.sesja)
    assert "uwaga-dyscyplina-zgloszenie" in tresc
    assert "uwaga-dyscyplina-pbn" not in tresc
    assert f"zgłoszenie publikacji:\n                        <strong>{s.d2}" in tresc


@pytest.mark.django_db
def test_bez_rozbieznosci_nie_ma_uwag_przy_autorze(
    importer_client, sesja_z_oswiadczeniem
):
    s = sesja_z_oswiadczeniem
    baker.make(Autor_Dyscyplina, autor=s.autor, rok=2024, dyscyplina_naukowa=s.d1)
    dolacz_profil_instytucji(s.sesja, s.sesja.created_by)

    assert uwagi_o_dyscyplinach(s.sesja) == {}
    assert "uwaga-dyscyplina" not in _autorzy(importer_client, s.sesja)


@pytest.mark.django_db
def test_bez_odpowiednika_w_pbn_profil_nie_jest_sprawdzany(importer_user):
    sesja = _sesja(importer_user, status=ImportSession.Status.FETCHED)

    assert dolacz_profil_instytucji(sesja, importer_user) is None


# --- Kreator: redaktor widzi, skąd są dane ------------------------------------


@pytest.mark.django_db
def test_weryfikacja_pokazuje_zrodla_danych(importer_client, importer_user):
    sesja = _sesja(
        importer_user,
        status=ImportSession.Status.FETCHED,
        normalized_data={
            "title": "Łączenie źródeł w praktyce",
            "doi": DOI,
            KLUCZ_ZRODEL: [
                {
                    "zrodlo": ZRODLO_PBN,
                    "stan": STAN_ZNALEZIONO,
                    "po": "DOI",
                    "identyfikator": PRACA_PBN,
                    "url": f"https://pbn.example/publication/{PRACA_PBN}",
                    "pola": ["streszczenie", "licencja"],
                    "autorzy": {"pbn_uid": 2, "orcid": 0, "dodani": 0},
                },
                {
                    "zrodlo": ZRODLO_PROFIL,
                    "stan": STAN_ZNALEZIONO,
                    "dyscypliny": 1,
                    "pominiete": 0,
                    "oswiadczenia": "pobrane z PBN",
                },
            ],
        },
    )

    tresc = importer_client.get(
        reverse("importer_publikacji:verify", kwargs={"session_id": sesja.pk})
    ).content.decode()

    assert "Źródła danych" in tresc
    assert "praca jest w PBN (znaleziona po DOI)" in tresc
    assert f"https://pbn.example/publication/{PRACA_PBN}" in tresc
    assert "Uzupełniono: streszczenie, licencja." in tresc
    assert "Identyfikatory osób w PBN uzupełniono 2 autorom." in tresc
    assert "Profil instytucji w PBN" in tresc
    assert "Dane z CrossRef, uzupełnione z: PBN" in tresc


@pytest.mark.django_db
def test_weryfikacja_starej_sesji_bez_panelu_zrodel(importer_client, importer_user):
    """Strażnik: sesje sprzed zmiany (bez informacji o źródłach) wyglądają
    jak dotąd."""
    sesja = _sesja(
        importer_user,
        status=ImportSession.Status.FETCHED,
        normalized_data={"title": "Stara sesja", "doi": DOI},
    )

    tresc = importer_client.get(
        reverse("importer_publikacji:verify", kwargs={"session_id": sesja.pk})
    ).content.decode()

    assert "Źródła danych" not in tresc
    assert "Dane z CrossRef" in tresc
    assert "uzupełnione z" not in tresc


@pytest.mark.django_db
def test_krok_autorow_pokazuje_podstawe_dopasowania(importer_client, importer_user):
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan")
    po_pbn = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid=osoba)
    po_orcid = baker.make(Autor, nazwisko="Nowak", imiona="Anna", orcid=ORCID_1)
    po_nazwisku = baker.make(Autor, nazwisko="Wiśniewski", imiona="Piotr")
    sesja = _sesja(importer_user, status=ImportSession.Status.SOURCE_MATCHED)
    for i, (autor, dane) in enumerate(
        [
            (po_pbn, {"pbn_uid": OSOBA_1}),
            (po_orcid, {"orcid": ORCID_1}),
            (po_nazwisku, {}),
        ]
    ):
        ImportedAuthor.objects.create(
            session=sesja,
            order=i,
            family_name=autor.nazwisko,
            given_name=autor.imiona,
            matched_autor=autor,
            match_status=ImportedAuthor.MatchStatus.AUTO_EXACT,
            **dane,
        )

    tresc = importer_client.get(
        reverse("importer_publikacji:authors", kwargs={"session_id": sesja.pk})
    ).content.decode()

    assert "po identyfikatorze PBN" in tresc
    assert "po ORCID" in tresc
    assert "po imieniu i nazwisku" in tresc


# --- Powiązanie rekordu z odpowiednikiem w PBN --------------------------------


@pytest.mark.django_db
def test_zajety_odpowiednik_pbn_nie_psuje_transakcji_tworzenia(importer_user):
    """Odpowiednik w PBN jest teraz ustawiany automatycznie, więc częściej
    trafi na rekord BPP, który już go ma. Tworzenie rekordu biegnie
    w transakcji — nieudane powiązanie nie może jej unieważnić."""
    praca = baker.make(Publication, mongoId=PRACA_PBN, versions=[])
    baker.make(Wydawnictwo_Zwarte, pbn_uid=praca)
    nowy = baker.make(Wydawnictwo_Zwarte)
    sesja = SimpleNamespace(matched_data={"pbn_mongo_id": PRACA_PBN})

    with transaction.atomic():
        _link_pbn_uid(sesja, nowy)
        # Bez savepointu to zapytanie rzuca TransactionManagementError.
        assert Wydawnictwo_Zwarte.objects.filter(pk=nowy.pk).exists()

    nowy.refresh_from_db()
    assert nowy.pbn_uid_id is None
    assert nowy.pbn_uid is None


# --- Poprawki po recenzji -----------------------------------------------------


def _uczelnia_z_pbn(uczelnia):
    uczelnia.pbn_app_name = "app"
    uczelnia.pbn_app_token = "token"
    uczelnia.pbn_api_root = "https://pbn.invalid"
    uczelnia.save()
    return uczelnia


@pytest.mark.django_db
def test_niedostepny_pbn_nie_wstrzymuje_importu(importer_user, uczelnia):
    """PBN nie odpowiada: zwykły klient ponawiałby połączenie 15 razy
    z długim timeoutem (ok. 8 minut) — a import po DOI z CrossRef w ogóle
    PBN-u nie potrzebuje. Drugie źródło dostaje jedną, krótką próbę."""
    proby = []

    def get(*args, **kw):
        proby.append(kw.get("timeout"))
        raise requests.exceptions.ConnectTimeout("PBN nie odpowiada")

    sesja = _sesja(importer_user, uczelnia=_uczelnia_z_pbn(uczelnia))
    dostawca = MagicMock()
    dostawca.fetch.return_value = _z_crossref()
    with (
        patch("importer_publikacji.tasks.get_provider", return_value=dostawca),
        patch("requests.get", side_effect=get),
        patch("pbn_client.transport.time.sleep") as spanie,
    ):
        fetch_session_task.apply(args=[sesja.pk, sesja.created_by_id]).get()

    sesja.refresh_from_db()
    assert sesja.status == ImportSession.Status.FETCHED
    assert _wpis(sesja, ZRODLO_PBN)["stan"] == STAN_NIE_SPRAWDZONO
    assert proby == [DOMYSLNY_TIMEOUT_DRUGIEGO_ZRODLA]
    spanie.assert_not_called()
    assert sesja.authors.count() == 2


def test_krotki_timeout_nie_zmienia_innych_klientow_pbn():
    """Strażnik: krótki timeout dotyczy jednego egzemplarza klienta."""
    from importer_publikacji.providers.pbn import _get_pbn_client

    uczelnia = MagicMock(
        pbn_app_name="app", pbn_app_token="token", pbn_api_root="https://pbn.invalid"
    )
    zwykly = _get_pbn_client(uczelnia)
    szybki = jedna_szybka_proba(_get_pbn_client(uczelnia))

    assert szybki.transport.timeout == DOMYSLNY_TIMEOUT_DRUGIEGO_ZRODLA
    assert zwykly.transport.timeout != DOMYSLNY_TIMEOUT_DRUGIEGO_ZRODLA
    assert "_make_get_request_with_retry" not in vars(zwykly.transport)


def test_crossref_jako_drugie_zrodlo_ma_krotki_timeout(monkeypatch):
    from importer_publikacji.providers import crossref as crossref_mod

    timeouty = []

    def get_by_doi(doi, timeout=None):
        timeouty.append(timeout)

    monkeypatch.setattr(
        crossref_mod.CrossrefAPICache, "objects", SimpleNamespace(get_by_doi=get_by_doi)
    )

    assert _prawdziwe_pobierz_z_crossref(DOI) is None
    assert timeouty == [DOMYSLNY_TIMEOUT_DRUGIEGO_ZRODLA]


@pytest.mark.django_db
def test_wolne_zrodlo_odswieza_modified_sesji(importer_user):
    """Przed każdym źródłem zadanie odświeża ``modified`` — strażnik nie
    weźmie wolnego, ale żywego pobierania za zawieszone."""
    sesja = _sesja(importer_user)
    stary = sesja.modified - timedelta(seconds=170)
    ImportSession.objects.filter(pk=sesja.pk).update(modified=stary)
    widziane = []

    def dolacz(session, result):
        widziane.append(ImportSession.objects.get(pk=sesja.pk).modified)
        return {"zrodlo": ZRODLO_PBN, "stan": STAN_BRAK}

    with patch("importer_publikacji.zrodla._dolacz_pbn", side_effect=dolacz):
        _pobierz(sesja, _z_crossref())

    assert widziane[0] > stary + timedelta(seconds=100)


@pytest.mark.django_db
def test_zastapione_zadanie_niczego_nie_zapisuje(importer_user):
    """Strażnik uznał sesję za zawieszoną i redaktor kliknął „Ponów”:
    stare zadanie, które dopiero teraz doczekało się odpowiedzi PBN, nie
    może dopisać autorów ani zmienić stanu sesji nowego zadania."""
    sesja = _sesja(importer_user)

    def dolacz(session, result):
        # W trakcie zapytania do PBN sesję przejęło nowe zadanie.
        ImportSession.objects.filter(pk=sesja.pk).update(celery_task_id="nowe-zadanie")
        return {"zrodlo": ZRODLO_PBN, "stan": STAN_BRAK}

    with patch("importer_publikacji.zrodla._dolacz_pbn", side_effect=dolacz):
        _pobierz(sesja, _z_crossref())

    assert sesja.status == ImportSession.Status.FETCHING
    assert sesja.celery_task_id == "nowe-zadanie"
    assert sesja.normalized_data == {}
    assert sesja.authors.count() == 0
    assert sesja.last_error_message == ""


@pytest.mark.django_db
def test_zadanie_sesji_oznaczonej_jako_zawieszona_wycofuje_sie(importer_user):
    sesja = _sesja(importer_user)

    def dolacz(session, result):
        ImportSession.objects.get(pk=sesja.pk).mark_stalled()
        return {"zrodlo": ZRODLO_PBN, "stan": STAN_BRAK}

    with patch("importer_publikacji.zrodla._dolacz_pbn", side_effect=dolacz):
        _pobierz(sesja, _z_crossref())

    assert sesja.status == ImportSession.Status.IMPORT_FAILED
    assert sesja.last_failed_stage == "fetch"
    assert sesja.authors.count() == 0


def test_rozne_pelne_imiona_nie_sa_laczone_po_inicjale():
    """„Kowalski Jan” nie dostaje identyfikatora „Kowalskiego Jerzego”."""
    glowne = _z_crossref(authors=[{"family": "Kowalski", "given": "Jan"}])
    dodatkowe = _z_crossref(
        authors=[{"family": "Kowalski", "given": "Jerzy", "pbn_uid": OSOBA_1}]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["pbn_uid"] == 0
    assert "pbn_uid" not in glowne.authors[0]


def test_dwie_osoby_o_tym_samym_zapisie_nie_dostaja_jednego_identyfikatora():
    glowne = _z_crossref(
        authors=[
            {"family": "Zhang", "given": "Wei"},
            {"family": "Nowak", "given": "Anna"},
            {"family": "Zhang", "given": "Wei"},
        ]
    )
    dodatkowe = _z_crossref(
        authors=[
            {"family": "Zhang", "given": "Wei", "pbn_uid": OSOBA_1},
            {"family": "Nowak", "given": "Anna", "pbn_uid": OSOBA_2},
        ]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["pbn_uid"] == 1
    assert [a.get("pbn_uid") for a in glowne.authors] == [None, OSOBA_2, None]


def test_drugie_imie_lub_inicjal_nie_przeszkadza_w_dopasowaniu():
    """Strażnik: „Jan A.” ↔ „Jan” oraz „J.” ↔ „Jan Adam” to ta sama osoba."""
    glowne = _z_crossref(
        authors=[
            {"family": "Kowalski", "given": "Jan A."},
            {"family": "Nowak", "given": "A."},
        ]
    )
    dodatkowe = _z_crossref(
        authors=[
            {"family": "Kowalski", "given": "Jan", "pbn_uid": OSOBA_1},
            {"family": "Nowak", "given": "Anna Maria", "pbn_uid": OSOBA_2},
        ]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["pbn_uid"] == 2


@pytest.mark.django_db
def test_praca_usunieta_w_pbn_nie_jest_wiazana(importer_user):
    usunieta = _praca_pbn()
    usunieta["status"] = "DELETED"

    sesja = _pobierz(_sesja(importer_user), _z_crossref(), _klient_pbn(po_doi=usunieta))

    wpis = _wpis(sesja, ZRODLO_PBN)
    assert wpis["stan"] == STAN_BRAK
    assert "usunięty" in wpis["komunikat"]
    assert "pbn_mongo_id" not in sesja.matched_data
    assert sesja.authors.get(order=0).pbn_uid == ""
    assert not Publication.objects.filter(pk=PRACA_PBN).exists()


@pytest.mark.django_db
def test_usunieta_ksiazka_w_wynikach_isbn_jest_pomijana(importer_user):
    client = _klient_pbn(
        po_isbn=[
            {"mongoId": PRACA_PBN, "status": "DELETED"},
            {"mongoId": KSIAZKA_PBN, "status": "ACTIVE"},
        ],
        po_id={KSIAZKA_PBN: _ksiazka_pbn()},
    )

    sesja = _pobierz(_sesja(importer_user), _ksiazka(), client)

    assert sesja.matched_data["pbn_mongo_id"] == KSIAZKA_PBN


@pytest.mark.django_db
def test_nieoczekiwany_blad_odswiezania_nie_wylacza_lokalnej_kopii(
    sesja_z_oswiadczeniem,
):
    s = sesja_z_oswiadczeniem
    with patch(
        "importer_publikacji.zrodla._odswiez_oswiadczenia",
        side_effect=RuntimeError("bum"),
    ):
        wpis = dolacz_profil_instytucji(s.sesja, s.sesja.created_by)

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina == s.d1
    assert wpis["stan"] == STAN_ZNALEZIONO
    assert wpis["oswiadczenia"] == "z lokalnej kopii danych PBN"


@pytest.mark.django_db
def test_uwaga_gdy_autor_spoza_uczelni_bez_przypisania(
    importer_client, sesja_z_oswiadczeniem
):
    """Autor bez przypisania na rok pracy, który nie jest autorem uczelni:
    dyscypliny z PBN nie przyjmujemy (FD#640), ale mówimy o tym przy
    autorze — i podajemy prawdziwy powód w ramce „Źródła danych”."""
    from bpp.models import Autor_Jednostka

    s = sesja_z_oswiadczeniem
    Autor_Jednostka.objects.filter(autor=s.autor).delete()
    Autor.objects.filter(pk=s.autor.pk).update(aktualna_jednostka=None)

    wpis = dolacz_profil_instytucji(s.sesja, s.sesja.created_by)
    s.sesja.normalized_data[KLUCZ_ZRODEL] = [wpis]
    s.sesja.save()

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina is None
    assert (wpis["pominiete"], wpis["pominiete_spoza"]) == (0, 1)
    uwaga = uwagi_o_dyscyplinach(s.sesja)[s.wiersz.pk]
    assert uwaga == {"pbn": s.d1, "przyjeta": None, "rok": 2024, "spoza_uczelni": True}

    tresc = _autorzy(importer_client, s.sesja)
    assert "uwaga-dyscyplina-spoza" in tresc
    assert "nie jest autorem uczelni" in tresc
    assert "nie zgadza się z przypisaniem" not in tresc


def _sesja_z_wpisem_pbn(importer_user, matched_data):
    return _sesja(
        importer_user,
        status=ImportSession.Status.FETCHED,
        matched_data=matched_data,
        normalized_data={
            "title": "Praca",
            "doi": DOI,
            KLUCZ_ZRODEL: [
                {
                    "zrodlo": ZRODLO_PBN,
                    "stan": STAN_ZNALEZIONO,
                    "po": "DOI",
                    "identyfikator": PRACA_PBN,
                    "url": "",
                    "pola": [],
                    "autorzy": {"pbn_uid": 0, "orcid": 0, "dodani": 0},
                }
            ],
        },
    )


@pytest.mark.django_db
def test_ramka_zrodel_nie_obiecuje_powiazania_po_usunieciu_odpowiednika(
    importer_client, importer_user
):
    obietnica = "Rekord zostanie powiązany z tym odpowiednikiem w PBN."

    aktualny = _sesja_z_wpisem_pbn(importer_user, {"pbn_mongo_id": PRACA_PBN})
    assert obietnica in _weryfikacja(importer_client, aktualny)

    usuniety = _sesja_z_wpisem_pbn(importer_user, {})
    tresc = _weryfikacja(importer_client, usuniety)
    assert obietnica not in tresc
    assert "rekord nie zostanie powiązany z PBN" in tresc

    zmieniony = _sesja_z_wpisem_pbn(importer_user, {"pbn_mongo_id": KSIAZKA_PBN})
    tresc = _weryfikacja(importer_client, zmieniony)
    assert obietnica not in tresc
    assert "wybrano potem inny" in tresc


@pytest.mark.django_db
def test_zajety_odpowiednik_pbn_jest_pokazany_redaktorowi(
    importer_client, importer_user
):
    praca = baker.make(Publication, mongoId=PRACA_PBN, versions=[])
    istniejacy = baker.make(
        Wydawnictwo_Zwarte, pbn_uid=praca, tytul_oryginalny="Rekord już w BPP"
    )
    sesja = _sesja_z_wpisem_pbn(importer_user, {"pbn_mongo_id": PRACA_PBN})

    tresc = _weryfikacja(importer_client, sesja)

    assert "Odpowiednik w PBN jest już zajęty" in tresc
    assert "Rekord już w BPP" in tresc
    assert istniejacy.get_absolute_url() in tresc
    assert "Rekord zostanie powiązany z tym odpowiednikiem w PBN." not in tresc

    wolny = _sesja_z_wpisem_pbn(importer_user, {"pbn_mongo_id": KSIAZKA_PBN})
    assert "Odpowiednik w PBN jest już zajęty" not in _weryfikacja(
        importer_client, wolny
    )
