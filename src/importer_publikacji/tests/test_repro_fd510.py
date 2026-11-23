"""FD#510: autor utworzony w importerze publikacji dostaje odpowiednik
w PBN, jeśli w danych pobranych z PBN jest jednoznacznie pasująca osoba.

Wcześniej importer szukał tylko wśród autorów BPP i każdy nowy autor
powstawał bez odpowiednika w PBN — nawet przy imporcie z PBN, który podaje
identyfikator osoby wprost.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.admin.models import LogEntry
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.providers.pbn import (
    PBNProvider,
    _extract_authors,
    pobierz_brakujace_osoby,
)
from importer_publikacji.views import _auto_match_authors
from pbn_api.exceptions import HttpException
from pbn_api.models import OsobaZInstytucji, Scientist

OSOBA_1 = "5e709189878c28a04737dc61"
OSOBA_2 = "5e709189878c28a04737dc62"
ORCID = "0000-0002-1825-0097"


def _osoba(pk, nazwisko, imiona, *, orcid=None, z_instytucji=False):
    obiekt = {"lastName": nazwisko, "name": imiona}
    if orcid:
        obiekt["orcid"] = orcid
    osoba = baker.make(
        Scientist, mongoId=pk, versions=[{"current": True, "object": obiekt}]
    )
    if z_instytucji:
        baker.make(
            OsobaZInstytucji, personId=osoba, firstName=imiona, lastName=nazwisko
        )
    return osoba


def _sesja(importer_user, *autorzy):
    sesja = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/fd510",
        raw_data={},
        normalized_data={},
    )
    for i, dane in enumerate(autorzy):
        ImportedAuthor.objects.create(
            session=sesja,
            order=i,
            match_status=ImportedAuthor.MatchStatus.UNMATCHED,
            **dane,
        )
    return sesja


def _utworz_niedopasowanych(importer_client, sesja):
    return importer_client.post(
        reverse(
            "importer_publikacji:authors-create-unmatched",
            kwargs={"session_id": sesja.pk},
        )
    )


@pytest.mark.django_db
def test_nowy_autor_z_odpowiednikiem_w_pbn_dostaje_pbn_uid(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Test odtwarzający: pracownik uczelni jest w danych z PBN, w BPP go
    nie ma — nowy autor ma zostać z nim powiązany."""
    _osoba(OSOBA_1, "Wiśniewska", "Halina", z_instytucji=True)
    sesja = _sesja(importer_user, {"family_name": "Wiśniewska", "given_name": "Halina"})

    response = _utworz_niedopasowanych(importer_client, sesja)

    assert response.status_code == 200
    autor = Autor.objects.get(nazwisko="Wiśniewska")
    assert autor.pbn_uid_id == OSOBA_1
    wiersz = sesja.authors.get()
    assert wiersz.matched_autor == autor
    assert wiersz.pbn_uwagi == ""
    assert "bez odpowiednika w PBN" not in response.content.decode()
    wpis = LogEntry.objects.get(content_type__model="autor", object_id=str(autor.pk))
    assert OSOBA_1 in wpis.change_message


@pytest.mark.django_db
def test_nowy_autor_po_orcid_dostaje_pbn_uid(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """ORCID wystarcza także dla osoby spoza instytucji, o innym zapisie
    nazwiska."""
    _osoba(OSOBA_1, "Smith", "John Adam", orcid=ORCID)
    sesja = _sesja(
        importer_user, {"family_name": "Smith", "given_name": "J.", "orcid": ORCID}
    )

    _utworz_niedopasowanych(importer_client, sesja)

    assert Autor.objects.get(nazwisko="Smith").pbn_uid_id == OSOBA_1


@pytest.mark.django_db
def test_nowy_autor_z_identyfikatorem_osoby_od_dostawcy(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Import z PBN podaje identyfikator osoby — to on decyduje, nie
    nazwisko (tu celowo inne niż w PBN)."""
    _osoba(OSOBA_1, "Nowak-Zamężna", "Ewa")
    sesja = _sesja(
        importer_user,
        {"family_name": "Nowak", "given_name": "Ewa", "pbn_uid": OSOBA_1},
    )

    _utworz_niedopasowanych(importer_client, sesja)

    assert Autor.objects.get(nazwisko="Nowak").pbn_uid_id == OSOBA_1


@pytest.mark.django_db
def test_niejednoznaczne_dopasowanie_tworzy_autora_bez_pbn_uid(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Dwie osoby o tym samym imieniu i nazwisku — nie zgadujemy."""
    _osoba(OSOBA_1, "Kowalski", "Jan", z_instytucji=True)
    _osoba(OSOBA_2, "Kowalski", "Jan", z_instytucji=True)
    sesja = _sesja(importer_user, {"family_name": "Kowalski", "given_name": "Jan"})

    response = _utworz_niedopasowanych(importer_client, sesja)

    autor = Autor.objects.get(nazwisko="Kowalski")
    assert autor.pbn_uid_id is None
    wiersz = sesja.authors.get()
    assert OSOBA_1 in wiersz.pbn_uwagi and OSOBA_2 in wiersz.pbn_uwagi
    tresc = response.content.decode()
    assert "bez odpowiednika w PBN" in tresc
    assert "pasuje kilka osób w PBN" in tresc


@pytest.mark.django_db
def test_osoba_spoza_instytucji_po_samym_nazwisku_nie_jest_dopasowywana(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Strażnik: zbieżność imienia i nazwiska z osobą, która nie pracuje
    w instytucji, to za mało na automatyczne powiązanie."""
    _osoba(OSOBA_1, "Smith", "John")
    sesja = _sesja(importer_user, {"family_name": "Smith", "given_name": "John"})

    _utworz_niedopasowanych(importer_client, sesja)

    assert Autor.objects.get(nazwisko="Smith").pbn_uid_id is None
    assert "Nie znaleziono" in sesja.authors.get().pbn_uwagi


@pytest.mark.django_db
def test_osoba_pbn_ma_juz_autora_nie_powstaje_duplikat(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Identyfikator osoby wskazuje autora, który już jest w BPP (pod innym
    zapisem nazwiska) — wiersz dostaje tego autora, nowy nie powstaje."""
    osoba = _osoba(OSOBA_1, "Nowak-Zamężna", "Ewa")
    istniejacy = baker.make(
        Autor, nazwisko="Nowak-Zamężna", imiona="Ewa", pbn_uid=osoba
    )
    sesja = _sesja(
        importer_user,
        {"family_name": "Nowak", "given_name": "E.", "pbn_uid": OSOBA_1},
    )
    przed = Autor.objects.count()

    _utworz_niedopasowanych(importer_client, sesja)

    assert Autor.objects.count() == przed
    assert sesja.authors.get().matched_autor == istniejacy


@pytest.mark.django_db
def test_po_nazwisku_osoba_juz_przypisana_nowy_autor_bez_pbn_uid(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Operator świadomie tworzy nowego autora o nazwisku osoby, która ma
    już autora w BPP: nowy powstaje, ale bez drugiego powiązania z tą samą
    osobą PBN."""
    osoba = _osoba(OSOBA_1, "Zielińska", "Anna", z_instytucji=True)
    istniejacy = baker.make(Autor, nazwisko="Zielińska", imiona="Anna", pbn_uid=osoba)
    sesja = _sesja(importer_user, {"family_name": "Zielińska", "given_name": "Anna"})

    _utworz_niedopasowanych(importer_client, sesja)

    nowy = sesja.authors.get().matched_autor
    assert nowy != istniejacy
    assert nowy.pbn_uid_id is None
    assert "możliwy duplikat" in sesja.authors.get().pbn_uwagi


@pytest.mark.django_db
def test_krok_autorzy_mowi_ilu_nie_bedzie_mialo_odpowiednika(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    _osoba(OSOBA_1, "Wiśniewska", "Halina", z_instytucji=True)
    sesja = _sesja(
        importer_user,
        {"family_name": "Wiśniewska", "given_name": "Halina"},
        {"family_name": "Obcy", "given_name": "Autor"},
        {"family_name": "Drugi", "given_name": "Obcy"},
    )

    response = importer_client.get(
        reverse("importer_publikacji:authors", kwargs={"session_id": sesja.pk}),
        HTTP_HX_REQUEST="true",
    )

    tresc = response.content.decode()
    assert "Bez odpowiednika w PBN: 2 z 3" in tresc
    assert response.context["bez_odpowiednika_pbn"] == 2


# --- Dostawca PBN ------------------------------------------------------------


def test_dostawca_pbn_zachowuje_identyfikator_osoby():
    autorzy = _extract_authors(
        {
            "authors": {
                OSOBA_1: {"lastName": "Kowalski", "name": "Jan"},
                OSOBA_2: {"lastName": "Nowak", "name": "Anna", "orcid": ORCID},
            }
        }
    )

    assert [a["pbn_uid"] for a in autorzy] == [OSOBA_1, OSOBA_2]
    assert [a["orcid"] for a in autorzy] == ["", ORCID]


@patch("importer_publikacji.providers.pbn._save_to_pbn_publication")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_dostawca_pbn_fetch_przenosi_identyfikatory_osob(mock_get_client, _mock_save):
    mock_get_client.return_value = MagicMock(
        get_publication_by_id=MagicMock(
            return_value={
                "mongoId": "5e709189878c28a04737dc6f",
                "versions": [
                    {
                        "current": True,
                        "object": {
                            "title": "Praca",
                            "type": "ARTICLE",
                            "authors": {
                                OSOBA_1: {"lastName": "Kowalski", "name": "Jan"}
                            },
                        },
                    }
                ],
            }
        )
    )

    pub = PBNProvider().fetch("5e709189878c28a04737dc6f")

    assert pub.authors == [
        {"family": "Kowalski", "given": "Jan", "orcid": "", "pbn_uid": OSOBA_1}
    ]


# --- Dopasowanie do autorów BPP ---------------------------------------------


@pytest.mark.django_db
def test_dopasowanie_po_identyfikatorze_osoby_wygrywa_z_nazwiskiem(importer_user):
    """Identyfikator osoby to najmocniejszy klucz: wskazuje autora BPP
    mimo innego zapisu nazwiska i mimo imiennika."""
    osoba = _osoba(OSOBA_1, "Nowak-Zamężna", "Ewa")
    wlasciwy = baker.make(Autor, nazwisko="Nowak-Zamężna", imiona="Ewa", pbn_uid=osoba)
    baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    sesja = _sesja(importer_user)

    _auto_match_authors(
        sesja, [{"family": "Nowak", "given": "Ewa", "pbn_uid": OSOBA_1}], 2024
    )

    wiersz = sesja.authors.get()
    assert wiersz.matched_autor == wlasciwy
    assert wiersz.match_status == ImportedAuthor.MatchStatus.AUTO_EXACT
    assert wiersz.pbn_uid == OSOBA_1


@pytest.mark.django_db
def test_straznik_dopasowanie_bez_identyfikatora_jak_dotad(importer_user):
    """Dane bez identyfikatora osoby (CrossRef) — dopasowanie po ORCID
    i po nazwisku działa jak wcześniej."""
    po_orcid = baker.make(Autor, nazwisko="Inaczej", imiona="Zapisany", orcid=ORCID)
    po_nazwisku = baker.make(Autor, nazwisko="Wiśniewska", imiona="Halina")
    sesja = _sesja(importer_user)

    _auto_match_authors(
        sesja,
        [
            {"family": "Smith", "given": "John", "orcid": ORCID},
            {"family": "Wiśniewska", "given": "Halina", "orcid": ""},
            {"family": "Nieznany", "given": "Zupełnie", "orcid": ""},
        ],
        2024,
    )

    wiersze = list(sesja.authors.order_by("order"))
    assert wiersze[0].matched_autor == po_orcid
    assert wiersze[1].matched_autor == po_nazwisku
    assert wiersze[1].match_status == ImportedAuthor.MatchStatus.AUTO_EXACT
    assert wiersze[2].matched_autor is None
    assert wiersze[2].match_status == ImportedAuthor.MatchStatus.UNMATCHED
    assert {w.pbn_uid for w in wiersze} == {""}


@pytest.mark.django_db
def test_straznik_identyfikator_bez_autora_w_bpp_nie_blokuje_nazwiska(importer_user):
    """Identyfikator osoby, której nikt w BPP nie ma — dopasowanie po
    nazwisku nadal działa."""
    po_nazwisku = baker.make(Autor, nazwisko="Wiśniewska", imiona="Halina")
    sesja = _sesja(importer_user)

    _auto_match_authors(
        sesja,
        [{"family": "Wiśniewska", "given": "Halina", "pbn_uid": OSOBA_1}],
        2024,
    )

    assert sesja.authors.get().matched_autor == po_nazwisku


# --- Dociąganie osób z PBN ---------------------------------------------------


@pytest.mark.django_db
@patch("pbn_integrator.utils.scientists.pobierz_i_zapisz_dane_jednej_osoby")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_dociaga_tylko_osoby_ktorych_nie_ma_lokalnie(mock_get_client, mock_pobierz):
    _osoba(OSOBA_1, "Jest", "Lokalnie")

    assert pobierz_brakujace_osoby(None, [OSOBA_1, OSOBA_2, ""]) == 1

    mock_pobierz.assert_called_once_with(
        mock_get_client.return_value, OSOBA_2, from_institution_api=False
    )


@pytest.mark.django_db
@patch("pbn_integrator.utils.scientists.pobierz_i_zapisz_dane_jednej_osoby")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_blad_pbn_przy_dociaganiu_nie_przerywa_importu(mock_get_client, mock_pobierz):
    mock_pobierz.side_effect = HttpException(500, "/api/v1/person/x", "awaria")

    assert pobierz_brakujace_osoby(None, [OSOBA_1, OSOBA_2]) == 0
    assert mock_pobierz.call_count == 1


@pytest.mark.django_db
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_brak_konfiguracji_pbn_przy_dociaganiu(mock_get_client):
    mock_get_client.side_effect = ValueError("Brak konfiguracji PBN")

    assert pobierz_brakujace_osoby(None, [OSOBA_1]) == 0
