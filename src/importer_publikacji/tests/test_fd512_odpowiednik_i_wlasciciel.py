"""FD#512, druga recenzja: tożsamość autorów, zmiana odpowiednika w PBN,
własność zadania pobierania, niekompletne oświadczenia, prace usunięte
w PBN i zajęty odpowiednik.

Wszystko bez sieci: odpowiedzi PBN są podstawiane.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.db import transaction
from django.urls import reverse
from model_bakery import baker

from bpp import const
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.providers.pbn import PBNProvider, pobierz_brakujace_osoby
from importer_publikacji.tasks import fetch_session_task
from importer_publikacji.views.pbn_check import _link_pbn_uid
from importer_publikacji.views.pbn_search import (
    _search_pbn_equivalents,
    _select_pbn_equivalent,
)
from importer_publikacji.views.publikacja import _create_publication
from importer_publikacji.zrodla import (
    KLUCZ_ZRODEL,
    ZRODLO_PBN,
    ZRODLO_PROFIL,
    dolacz_profil_instytucji,
    uzupelnij_autorow,
)
from pbn_api.exceptions import HttpException
from pbn_api.models import Institution, OswiadczenieInstytucji, Publication

from .test_fd512_laczenie_zrodel import (
    DOI,
    KSIAZKA_PBN,
    ORCID_1,
    OSOBA_1,
    OSOBA_2,
    PRACA_PBN,
    _klient_pbn,
    _osoba,
    _pobierz,
    _praca_pbn,
    _sesja,
    _wpis,
    _z_crossref,
)

ORCID_2 = "0000-0001-5109-3700"
PRACA_B = KSIAZKA_PBN


# --- A. Sprzeczne ORCID-y ------------------------------------------------------


def test_rozne_orcidy_wykluczaja_dopasowanie_po_nazwisku():
    """CrossRef i PBN mają po jednym „Janie Kowalskim”, ale z różnymi
    numerami ORCID — to dwie różne osoby, identyfikator z PBN nie może
    trafić do autora z CrossRef."""
    glowne = _z_crossref(
        authors=[{"family": "Kowalski", "given": "Jan", "orcid": ORCID_1}]
    )
    dodatkowe = _z_crossref(
        authors=[
            {"family": "Kowalski", "given": "Jan", "orcid": ORCID_2, "pbn_uid": OSOBA_1}
        ]
    )

    assert uzupelnij_autorow(glowne, dodatkowe) == {
        "pbn_uid": 0,
        "orcid": 0,
        "dodani": 0,
    }
    assert "pbn_uid" not in glowne.authors[0]
    assert glowne.authors[0]["orcid"] == ORCID_1


def test_ten_sam_orcid_u_dwoch_osob_w_drugim_zrodle_nie_laczy():
    glowne = _z_crossref(
        authors=[{"family": "Kowalski", "given": "Jan", "orcid": ORCID_1}]
    )
    dodatkowe = _z_crossref(
        authors=[
            {"family": "Nowak", "given": "Adam", "orcid": ORCID_1, "pbn_uid": OSOBA_1},
            {"family": "Lis", "given": "Ewa", "orcid": ORCID_1, "pbn_uid": OSOBA_2},
        ]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["pbn_uid"] == 0


def test_orcid_po_jednej_stronie_nie_przeszkadza():
    """Strażnik: brak ORCID po jednej stronie to nie sprzeczność."""
    glowne = _z_crossref(
        authors=[{"family": "Kowalski", "given": "Jan", "orcid": ORCID_1}]
    )
    dodatkowe = _z_crossref(
        authors=[{"family": "Kowalski", "given": "Jan", "pbn_uid": OSOBA_1}]
    )

    assert uzupelnij_autorow(glowne, dodatkowe)["pbn_uid"] == 1


# --- B. Zmiana i usunięcie odpowiednika w kroku „Sprawdź w PBN” ----------------


def _oswiadczenie(praca, osoba, dyscyplina, instytucja):
    return baker.make(
        OswiadczenieInstytucji,
        publicationId=praca,
        personId=osoba,
        institutionId=instytucja,
        type="AUTHOR",
        inOrcid=False,
        disciplines={"name": dyscyplina.nazwa},
    )


@pytest.fixture
def po_imporcie(
    importer_user,
    uczelnia,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Import z CrossRef, przy którym importer sam znalazł w PBN pracę A.

    Z pracy A przyszły: identyfikator osoby (po nim rozpoznano autora BPP
    zapisanego inaczej niż w CrossRef), ORCID drugiego autora i dyscyplina
    z oświadczenia. W lokalnej kopii danych PBN jest też praca B z innym
    oświadczeniem tej samej osoby.
    """
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan")
    autor = baker.make(Autor, nazwisko="Kowalski-Zamężny", imiona="J", pbn_uid=osoba)
    autor.dodaj_jednostke(jednostka)
    # Obie dyscypliny są przypisane na rok pracy, więc importer sam nie
    # rozstrzygnie — robi to oświadczenie w PBN.
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )
    nowak = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    nowak.dodaj_jednostke(jednostka)

    instytucja = baker.make(Institution)
    dane_a = _praca_pbn(
        authors={
            OSOBA_1: {"lastName": "Kowalski", "name": "Jan"},
            OSOBA_2: {"lastName": "Nowak", "name": "Anna", "orcid": ORCID_2},
        }
    )
    dane_b = _praca_pbn(
        PRACA_B,
        title="Inna praca",
        authors={OSOBA_1: {"lastName": "Kowalski", "name": "Jan"}},
    )
    praca_a = baker.make(
        Publication, mongoId=PRACA_PBN, status="ACTIVE", versions=dane_a["versions"]
    )
    praca_b = baker.make(
        Publication, mongoId=PRACA_B, status="ACTIVE", versions=dane_b["versions"]
    )
    _osoba(OSOBA_2, "Nowak", "Anna")
    _oswiadczenie(praca_a, osoba, dyscyplina1, instytucja)
    _oswiadczenie(praca_b, osoba, dyscyplina2, instytucja)

    sesja = _pobierz(
        _sesja(importer_user, uczelnia=uczelnia),
        _z_crossref(
            authors=[
                {"family": "Kowalski", "given": "Jan", "orcid": ""},
                {"family": "Nowak", "given": "Anna", "orcid": ""},
            ]
        ),
        _klient_pbn(po_doi=dane_a),
    )
    sesja.charakter_formalny = charaktery_formalne["AC"]
    sesja.typ_kbn = Typ_KBN.objects.get(skrot="PO")
    sesja.jezyk = jezyki["pol."]
    sesja.status = ImportSession.Status.PUNKTACJA
    sesja.save()

    kowalski, anna = sesja.authors.order_by("order")
    # Stan wyjściowy — to wszystko pochodzi z pracy A.
    assert sesja.matched_data["pbn_mongo_id"] == PRACA_PBN
    assert (kowalski.pbn_uid, kowalski.matched_autor) == (OSOBA_1, autor)
    assert kowalski.matched_dyscyplina == dyscyplina1
    assert (anna.pbn_uid, anna.orcid, anna.matched_autor) == (OSOBA_2, ORCID_2, nowak)
    return SimpleNamespace(
        sesja=sesja,
        autor=autor,
        nowak=nowak,
        jednostka=jednostka,
        d1=dyscyplina1,
        d2=dyscyplina2,
        dane_b=dane_b,
    )


def _post(importer_client, nazwa, sesja, **dane):
    return importer_client.post(
        reverse(f"importer_publikacji:{nazwa}", kwargs={"session_id": sesja.pk}), dane
    )


def _autorzy_rekordu(rekord):
    return {wa.autor: wa.dyscyplina_naukowa for wa in rekord.autorzy_set.all()}


@pytest.mark.django_db
def test_usuniecie_odpowiednika_wycofuje_dane_z_tamtej_pracy(
    importer_client, po_imporcie
):
    """Redaktor uznał, że praca A z PBN to nie ta praca i wyczyścił wybór:
    identyfikatory osób, ORCID i dyscyplina wzięte z A nie mogą zostać."""
    s = po_imporcie

    _post(importer_client, "pbn-clear", s.sesja)

    s.sesja.refresh_from_db()
    assert "pbn_mongo_id" not in s.sesja.matched_data
    kowalski, anna = s.sesja.authors.order_by("order")
    assert kowalski.pbn_uid == ""
    # Autora BPP rozpoznano wyłącznie po identyfikatorze z pracy A.
    assert kowalski.matched_autor is None
    assert kowalski.match_status == ImportedAuthor.MatchStatus.UNMATCHED
    assert kowalski.matched_dyscyplina is None
    assert kowalski.dyscyplina_source == ""
    # ORCID z pracy A nie może trafić do kartoteki autora BPP.
    assert (anna.pbn_uid, anna.orcid) == ("", "")
    # „Nowak Anna” jest rozpoznawalna po samym nazwisku — zostaje.
    assert anna.matched_autor == s.nowak
    assert s.sesja.normalized_data["abstract"] is None
    wpis = _wpis(s.sesja, ZRODLO_PBN)
    assert wpis["wycofano"] is True
    assert not [
        w for w in s.sesja.normalized_data[KLUCZ_ZRODEL] if w["zrodlo"] == ZRODLO_PROFIL
    ]


@pytest.mark.django_db
def test_wybor_a_usuniecie_zapis(importer_client, po_imporcie):
    """Pełna ścieżka: wybór A → usunięcie → zapis. Rekord nie dostaje ani
    powiązania z PBN, ani dyscypliny z oświadczenia pracy A."""
    s = po_imporcie
    _post(importer_client, "pbn-clear", s.sesja)
    # Redaktor ręcznie wskazuje autora, którego importer już nie rozpoznaje.
    wiersz = s.sesja.authors.get(order=0)
    wiersz.matched_autor = s.autor
    wiersz.matched_jednostka = s.jednostka
    wiersz.match_status = ImportedAuthor.MatchStatus.MANUAL
    wiersz.save()
    s.sesja.refresh_from_db()

    rekord = _create_publication(s.sesja)

    assert rekord.pbn_uid_id is None
    assert _autorzy_rekordu(rekord)[s.autor] is None
    s.nowak.refresh_from_db()
    assert not s.nowak.orcid


@pytest.mark.django_db
def test_wybor_a_zmiana_na_b_zapis(importer_client, importer_user, po_imporcie):
    """Pełna ścieżka: wybór A → zmiana na B → zapis. Dane z A są wycofane,
    a w ich miejsce wchodzą dane pracy B (osoby i jej oświadczenia)."""
    s = po_imporcie
    client = MagicMock()
    client.get_publication_by_id.return_value = s.dane_b
    importer_user.pbn_token = "token"

    with patch.object(type(s.sesja.uczelnia), "pbn_client", return_value=client):
        _post(importer_client, "pbn-select", s.sesja, mongo_id=PRACA_B)

    s.sesja.refresh_from_db()
    assert s.sesja.matched_data["pbn_mongo_id"] == PRACA_B
    kowalski, anna = s.sesja.authors.order_by("order")
    # Kowalski jest i w pracy B — identyfikator wraca, już z B.
    assert (kowalski.pbn_uid, kowalski.matched_autor) == (OSOBA_1, s.autor)
    assert kowalski.matched_dyscyplina == s.d2
    assert kowalski.dyscyplina_source == ImportedAuthor.DyscyplinaSource.PBN_PROFIL
    # Nowak w pracy B nie ma — jej identyfikator i ORCID z A znikają.
    assert (anna.pbn_uid, anna.orcid) == ("", "")
    stany = [
        (w["zrodlo"], w.get("identyfikator"), bool(w.get("wycofano")))
        for w in s.sesja.normalized_data[KLUCZ_ZRODEL]
        if w["zrodlo"] == ZRODLO_PBN
    ]
    assert stany == [(ZRODLO_PBN, PRACA_PBN, True), (ZRODLO_PBN, PRACA_B, False)]

    rekord = _create_publication(s.sesja)

    assert rekord.pbn_uid_id == PRACA_B
    assert _autorzy_rekordu(rekord)[s.autor] == s.d2


@pytest.mark.django_db
def test_zmiana_odpowiednika_zachowuje_decyzje_redaktora(importer_client, po_imporcie):
    """Strażnik: ręcznie wskazany autor i ręcznie wybrana dyscyplina
    zostają, cokolwiek stanie się z odpowiednikiem."""
    s = po_imporcie
    wiersz = s.sesja.authors.get(order=0)
    wiersz.match_status = ImportedAuthor.MatchStatus.MANUAL
    wiersz.matched_dyscyplina = s.d2
    wiersz.dyscyplina_source = ImportedAuthor.DyscyplinaSource.MANUAL
    wiersz.save()

    _post(importer_client, "pbn-clear", s.sesja)

    wiersz.refresh_from_db()
    assert wiersz.matched_autor == s.autor
    assert wiersz.match_status == ImportedAuthor.MatchStatus.MANUAL
    assert wiersz.matched_dyscyplina == s.d2
    assert wiersz.dyscyplina_source == ImportedAuthor.DyscyplinaSource.MANUAL
    # Sam identyfikator z odrzuconej pracy znika także z ręcznego wiersza.
    assert wiersz.pbn_uid == ""


@pytest.mark.django_db
def test_ponowny_wybor_tego_samego_odpowiednika_niczego_nie_rusza(
    importer_client, importer_user, po_imporcie
):
    s = po_imporcie
    client = MagicMock()
    client.get_publication_by_id.return_value = _praca_pbn()
    with patch.object(type(s.sesja.uczelnia), "pbn_client", return_value=client):
        _post(importer_client, "pbn-select", s.sesja, mongo_id=PRACA_PBN)

    kowalski = s.sesja.authors.get(order=0)
    assert (kowalski.pbn_uid, kowalski.matched_dyscyplina) == (OSOBA_1, s.d1)
    s.sesja.refresh_from_db()
    assert not _wpis(s.sesja, ZRODLO_PBN).get("wycofano")


# --- C. Własność zadania pobierania -------------------------------------------


def _przejmij(sesja):
    ImportSession.objects.filter(pk=sesja.pk).update(celery_task_id="nowe-zadanie")


@pytest.mark.django_db
def test_zastapione_zadanie_nie_stosuje_dyscyplin_ani_nie_zapisuje_zrodel(
    importer_user, uczelnia, jednostka, dyscyplina1
):
    """Sesję przejęło nowe zadanie w trakcie pobierania oświadczeń z PBN:
    stare nie może już ustawić dyscyplin ani nadpisać ``normalized_data``."""
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid=osoba)
    autor.dodaj_jednostke(jednostka)
    dane = _praca_pbn()
    praca = baker.make(Publication, mongoId=PRACA_PBN, versions=dane["versions"])
    _oswiadczenie(praca, osoba, dyscyplina1, baker.make(Institution))
    sesja = _sesja(importer_user, uczelnia=uczelnia)

    def odswiez(session, user, mongo_id):
        _przejmij(sesja)
        return "pobrane z PBN"

    with patch("importer_publikacji.zrodla._odswiez_oswiadczenia", side_effect=odswiez):
        _pobierz(sesja, _z_crossref(), _klient_pbn(po_doi=dane))

    assert sesja.status == ImportSession.Status.FETCHING
    assert sesja.celery_task_id == "nowe-zadanie"
    wiersz = sesja.authors.get(order=0)
    assert wiersz.matched_dyscyplina is None
    assert wiersz.dyscyplina_source == ""
    assert ZRODLO_PROFIL not in [
        w["zrodlo"] for w in sesja.normalized_data.get(KLUCZ_ZRODEL, [])
    ]


@pytest.mark.django_db
def test_blad_zastapionego_zadania_nie_oznacza_sesji_jako_nieudanej(importer_user):
    sesja = _sesja(importer_user)

    def bum(*args, **kw):
        _przejmij(sesja)
        raise RuntimeError("bum")

    dostawca = MagicMock()
    dostawca.fetch.return_value = _z_crossref()
    with (
        patch("importer_publikacji.tasks.get_provider", return_value=dostawca),
        patch("importer_publikacji.tasks._auto_match_type_and_language", bum),
    ):
        # Sam błąd nadal jest zgłaszany (monitoring) — nie zmienia tylko sesji.
        with pytest.raises(RuntimeError):
            fetch_session_task.apply(args=[sesja.pk, sesja.created_by_id]).get()

    sesja.refresh_from_db()
    assert sesja.status == ImportSession.Status.FETCHING
    assert sesja.celery_task_id == "nowe-zadanie"
    assert sesja.last_error_message == ""


@pytest.mark.django_db
def test_identyfikator_zadania_jest_zapisany_przed_wyslaniem(
    importer_client, importer_user
):
    """„Ponów” i start importu zapisują identyfikator zadania PRZED jego
    wysłaniem — stare zadanie od razu widzi, że sesja ma nowego właściciela."""
    sesja = _sesja(
        importer_user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="fetch",
    )
    widziane = []

    def wyslij(args=None, task_id=None, **kw):
        stan = ImportSession.objects.get(pk=args[0])
        widziane.append((stan.status, stan.celery_task_id, task_id))

    with patch("importer_publikacji.views.retry.fetch_session_task") as zadanie:
        zadanie.apply_async.side_effect = wyslij
        _post(importer_client, "task-retry", sesja)

    ((status, zapisany, wyslany),) = widziane
    assert status == ImportSession.Status.FETCHING
    assert zapisany and zapisany == wyslany

    with patch("importer_publikacji.views.wizard.fetch_session_task") as zadanie:
        zadanie.apply_async.side_effect = wyslij
        importer_client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "CrossRef", "identifier": "10.1234/fd512.nowy"},
        )

    status, zapisany, wyslany = widziane[1]
    assert status == ImportSession.Status.FETCHING
    assert zapisany and zapisany == wyslany


def test_pobieranie_osob_odswieza_sesje_i_ma_limit_czasu():
    """Do 50 osób po kilkanaście sekund każda przekroczyłoby próg strażnika
    (180 s) — pętla daje znak życia i ma łączny limit czasu."""
    znaki = []
    pobrane = []
    zegar = iter([0, 0, 10, 20, 30, 40, 50, 60, 70])

    with (
        patch("importer_publikacji.providers.pbn.Scientist", create=True),
        patch("pbn_api.models.Scientist.objects") as osoby,
        patch("importer_publikacji.providers.pbn._get_pbn_client"),
        patch(
            "pbn_integrator.utils.scientists.pobierz_i_zapisz_dane_jednej_osoby",
            side_effect=lambda client, pk, **kw: pobrane.append(pk),
        ),
        patch("importer_publikacji.providers.pbn.time.monotonic", lambda: next(zegar)),
    ):
        osoby.filter.return_value.values_list.return_value = []
        ile = pobierz_brakujace_osoby(
            MagicMock(),
            ["a" * 24, "b" * 24, "c" * 24, "d" * 24, "e" * 24],
            znak_zycia=lambda: znaki.append(1),
            limit_czasu=25,
        )

    # Zegar: start 0, przed osobami 0/10/20 — mieści się; przed czwartą 30 > 25.
    assert ile == len(pobrane) == 3
    assert len(znaki) == 3


# --- D. Niekompletne oświadczenia ---------------------------------------------


@pytest.mark.django_db
def test_niekompletne_oswiadczenia_z_pbn_nie_kasuja_lokalnej_kopii(
    importer_user, uczelnia, jednostka, dyscyplina1
):
    """PBN zwraca oświadczenie osoby, której nie ma w lokalnej kopii, a jej
    pobranie kończy się błędem 500: zapis oświadczenia jest po cichu
    pomijany. Bez zabezpieczenia stare oświadczenia znikały, a importer
    opisywał wynik jako „pobrany z PBN”."""
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid=osoba)
    autor.dodaj_jednostke(jednostka)
    instytucja = baker.make(Institution)
    praca = baker.make(Publication, mongoId=PRACA_PBN, versions=[])
    _oswiadczenie(praca, osoba, dyscyplina1, instytucja)
    sesja = _sesja(
        importer_user,
        uczelnia=uczelnia,
        status=ImportSession.Status.FETCHED,
        normalized_data={"year": 2024},
        matched_data={"pbn_mongo_id": PRACA_PBN},
    )
    ImportedAuthor.objects.create(
        session=sesja,
        order=0,
        family_name="Kowalski",
        given_name="Jan",
        matched_autor=autor,
        matched_jednostka=jednostka,
        match_status=ImportedAuthor.MatchStatus.AUTO_EXACT,
    )

    from pbn_api.client import BppPBNClient

    class Klient(MagicMock):
        """Klient PBN z prawdziwą logiką pobierania oświadczeń i podstawioną
        odpowiedzią serwera."""

        uczelnia = sesja.uczelnia

        def get_institution_statements_of_single_publication(self, pk, *args):
            return [
                {
                    "id": "0a1b2c3d-0000-4000-8000-000000000001",
                    "institutionId": instytucja.pk,
                    "personId": OSOBA_2,
                    "publicationId": PRACA_PBN,
                    "addedTimestamp": "2024.05.16",
                    "inOrcid": False,
                    "type": "AUTHOR",
                    "disciplines": {"name": dyscyplina1.nazwa},
                }
            ]

        def download_statements_of_publication(self, pub):
            return BppPBNClient.download_statements_of_publication(self, pub)

    uzytkownik = MagicMock(pbn_token="token")
    uzytkownik.pbn_token_possibly_valid.return_value = True
    with (
        patch.object(type(sesja.uczelnia), "pbn_client", return_value=Klient()),
        patch(
            "pbn_integrator.utils.mongodb_ops.ensure_person_exists",
            side_effect=HttpException(500, "/api/v1/person/", "Internal error"),
        ),
    ):
        wpis = dolacz_profil_instytucji(sesja, uzytkownik)

    assert OswiadczenieInstytucji.objects.filter(publicationId=praca).count() == 1
    assert wpis["oswiadczenia"] == "z lokalnej kopii danych PBN"
    assert wpis["dyscypliny"] == 1


# --- E. Prace usunięte w PBN przy wyborze ręcznym -----------------------------


def _usunieta(mongo_id=PRACA_PBN):
    dane = _praca_pbn(mongo_id)
    dane["status"] = "DELETED"
    return dane


@pytest.mark.django_db
def test_reczny_wybor_nie_przyjmuje_pracy_usunietej_w_pbn(importer_user, uczelnia):
    sesja = _sesja(
        importer_user, uczelnia=uczelnia, status=ImportSession.Status.FETCHED
    )
    client = MagicMock()
    client.get_publication_by_id.return_value = _usunieta()

    with patch.object(type(uczelnia), "pbn_client", return_value=client):
        assert (
            _select_pbn_equivalent(sesja, MagicMock(pbn_token="t"), PRACA_PBN) is False
        )

    sesja.refresh_from_db()
    assert "pbn_mongo_id" not in sesja.matched_data


@pytest.mark.django_db
def test_reczny_wybor_nie_przyjmuje_usunietej_pracy_z_lokalnej_kopii(
    importer_user, uczelnia
):
    """PBN nie odpowiada, a lokalna kopia zna pracę jako usuniętą."""
    baker.make(Publication, mongoId=PRACA_PBN, status="DELETED", versions=[])
    sesja = _sesja(
        importer_user, uczelnia=uczelnia, status=ImportSession.Status.FETCHED
    )
    client = MagicMock()
    client.get_publication_by_id.side_effect = HttpException(500, "/x", "bum")

    with patch.object(type(uczelnia), "pbn_client", return_value=client):
        assert (
            _select_pbn_equivalent(sesja, MagicMock(pbn_token="t"), PRACA_PBN) is False
        )


def test_wyszukiwanie_w_kroku_sprawdz_w_pbn_pomija_prace_usuniete():
    client = MagicMock()
    client.search_publications.side_effect = lambda **kw: iter(
        [
            {"mongoId": PRACA_PBN, "status": "DELETED", "title": "Usunięta"},
            {"mongoId": PRACA_B, "status": "ACTIVE", "title": "Aktywna"},
        ]
    )
    uczelnia = MagicMock(pbn_api_root="https://pbn.example")
    uczelnia.pbn_client.return_value = client
    sesja = SimpleNamespace(
        uczelnia=uczelnia,
        normalized_data={"title": "Praca", "doi": DOI, "isbn": "9788301000001"},
    )

    with patch("importer_publikacji.views.pbn_search._search_pbn_local_www") as www:
        www.return_value = []
        wynik = _search_pbn_equivalents(sesja, MagicMock(pbn_token="t"))

    for os_ in ("by_doi", "by_title", "by_isbn"):
        assert [r["mongo_id"] for r in wynik[os_]] == [PRACA_B]


@pytest.mark.django_db
def test_import_po_identyfikatorze_pracy_usunietej_w_pbn(importer_user, uczelnia):
    """Import bezpośrednio z PBN pracy usuniętej: nie powstaje sesja
    z danymi, a redaktor dostaje wyraźny powód."""
    client = MagicMock()
    client.get_publication_by_id.return_value = _usunieta()
    sesja = _sesja(
        importer_user, provider="PBN", uczelnia=uczelnia, identifier=PRACA_PBN
    )

    with patch(
        "importer_publikacji.providers.pbn._get_pbn_client", return_value=client
    ):
        dostawca = PBNProvider()
        dostawca.uczelnia = uczelnia
        assert dostawca.fetch(PRACA_PBN) is None
        fetch_session_task.apply(args=[sesja.pk, sesja.created_by_id]).get()

    sesja.refresh_from_db()
    assert sesja.status == ImportSession.Status.IMPORT_FAILED
    assert "usunięta w PBN" in sesja.last_error_message
    assert "pbn_mongo_id" not in sesja.matched_data


# --- F. Zajęty odpowiednik: ta sama reguła przy zapisie i w komunikacie --------


@pytest.mark.django_db
def test_odpowiednik_zajety_w_innej_tabeli_nie_jest_wiazany_drugi_raz():
    """Unikalność w bazie działa osobno w każdej tabeli wydawnictw:
    odpowiednik przypisany do wydawnictwa ciągłego dałoby się zapisać
    drugi raz w zwartym — wbrew ostrzeżeniu „nie zostanie powiązany”."""
    praca = baker.make(Publication, mongoId=PRACA_PBN, status="ACTIVE", versions=[])
    baker.make(Wydawnictwo_Ciagle, pbn_uid=praca)
    nowy = baker.make(Wydawnictwo_Zwarte)
    sesja = SimpleNamespace(matched_data={"pbn_mongo_id": PRACA_PBN})

    with transaction.atomic():
        _link_pbn_uid(sesja, nowy)

    nowy.refresh_from_db()
    assert nowy.pbn_uid_id is None


@pytest.mark.django_db
def test_wolny_odpowiednik_jest_wiazany():
    """Strażnik: zwykłe powiązanie działa jak dotąd."""
    baker.make(Publication, mongoId=PRACA_PBN, status="ACTIVE", versions=[])
    nowy = baker.make(Wydawnictwo_Zwarte)

    with transaction.atomic():
        _link_pbn_uid(SimpleNamespace(matched_data={"pbn_mongo_id": PRACA_PBN}), nowy)

    nowy.refresh_from_db()
    assert nowy.pbn_uid_id == PRACA_PBN


assert const.TO_AUTOR == 0  # role w danych testowych: domyślnie autor
