"""FD#512: importer publikacji łączy źródła danych.

Import zaczęty od DOI (CrossRef) sam sprawdza, czy praca jest w PBN — po
DOI, a książkę także po ISBN — i dociąga stamtąd odpowiednik w PBN,
identyfikatory osób i brakujące pola. Import zaczęty od PBN sprawdza
CrossRef po DOI. Dyscypliny przychodzą z oświadczeń w profilu instytucji.
Redaktor widzi w kreatorze, skąd pochodzi która informacja.

Wszystko bez sieci: odpowiedzi PBN i CrossRef są podstawiane.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
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
    KLUCZ_ZRODEL,
    STAN_BRAK,
    STAN_NIE_SPRAWDZONO,
    STAN_NIEJEDNOZNACZNE,
    STAN_ZNALEZIONO,
    ZRODLO_CROSSREF,
    ZRODLO_PBN,
    ZRODLO_PROFIL,
    dolacz_profil_instytucji,
    polacz_zrodla,
    uzupelnij_autorow,
    uzupelnij_brakujace_pola,
    zastosuj_dyscypliny_z_profilu,
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

    with patch("importer_publikacji.providers.get_provider") as get_provider:
        (wpis,) = polacz_zrodla(sesja, wynik)

    get_provider.assert_not_called()
    assert wpis["stan"] == STAN_NIE_SPRAWDZONO
    assert sesja.matched_data == {"pbn_mongo_id": PRACA_PBN}


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

    assert zastosuj_dyscypliny_z_profilu(s.sesja) == (0, 0)

    s.wiersz.refresh_from_db()
    assert s.wiersz.matched_dyscyplina == s.d2
    assert s.wiersz.dyscyplina_source == zrodlo


@pytest.mark.django_db
def test_oswiadczenie_redaktora_nie_trafia_do_autora(sesja_z_oswiadczeniem):
    s = sesja_z_oswiadczeniem
    OswiadczenieInstytucji.objects.update(type="EDITOR")

    assert zastosuj_dyscypliny_z_profilu(s.sesja) == (0, 0)


@pytest.mark.django_db
def test_redaktor_zalogowany_do_pbn_odswieza_oswiadczenia(sesja_z_oswiadczeniem):
    s = sesja_z_oswiadczeniem
    client = MagicMock()
    uzytkownik = MagicMock(pbn_token="token")
    uzytkownik.pbn_token_possibly_valid.return_value = True

    with patch.object(type(s.sesja.uczelnia), "pbn_client", return_value=client):
        wpis = dolacz_profil_instytucji(s.sesja, uzytkownik)

    client.download_statements_of_publication.assert_called_once()
    assert client.download_statements_of_publication.call_args.args[0].pk == PRACA_PBN
    assert wpis["oswiadczenia"] == "pobrane z PBN"


@pytest.mark.django_db
def test_blad_pbn_przy_oswiadczeniach_zostawia_lokalna_kopie(sesja_z_oswiadczeniem):
    s = sesja_z_oswiadczeniem
    client = MagicMock()
    client.download_statements_of_publication.side_effect = HttpException(
        403, "/api/v1/institutionProfile/", "Forbidden"
    )
    uzytkownik = MagicMock(pbn_token="token")
    uzytkownik.pbn_token_possibly_valid.return_value = True

    with patch.object(type(s.sesja.uczelnia), "pbn_client", return_value=client):
        wpis = dolacz_profil_instytucji(s.sesja, uzytkownik)

    assert wpis["oswiadczenia"] == "z lokalnej kopii danych PBN"
    assert wpis["dyscypliny"] == 1


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
