"""FD#517: przypadki z drugiej recenzji „Wzbogać z …” — każdy test odtwarza
zgłoszony problem (padał przed poprawką)."""

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle
from crossref_bpp.models import CrossrefAPICache
from import_common import porownanie_pol as reguly
from importer_publikacji.models import ImportSession
from importer_publikacji.providers.crossref import CrossRefProvider
from importer_publikacji.wzbogacanie import dodawanie_autorow
from importer_publikacji.wzbogacanie.autorzy import (
    BRAK_W_BPP,
    DO_SPRAWDZENIA,
    TYLKO_W_BPP,
    ZGODNY,
    porownaj_autorow,
)
from importer_publikacji.wzbogacanie.pola import BRAK_W_ZRODLE, ZGODNE, porownaj

pytestmark = pytest.mark.django_db

DOI = "10.1234/test.2024.001"
ZID = f"doi:{DOI}"


def _url(rekord, zrodlo="crossref", nazwa="wzbogac"):
    return reverse(f"admin:bpp_wydawnictwo_ciagle_{nazwa}", args=(rekord.pk, zrodlo))


def _w(rekord):
    return {w.klucz: w for w in porownaj(rekord, CrossRefProvider().fetch(DOI))}


@pytest.fixture
def crossref(sample_crossref_data):
    CrossrefAPICache.objects.create(doi=DOI, data=sample_crossref_data)
    return sample_crossref_data


@pytest.fixture
def rekord(wydawnictwo_ciagle, crossref):
    w = wydawnictwo_ciagle
    w.doi = DOI
    w.strony = "1-2"
    w.save()
    return w


# --- 1. Zakres uczelni (instalacja wielouczelniana) -------------------------


@pytest.fixture
def redaktor(client, uczelnia):
    """Redaktor (nie superużytkownik) pracujący w domenie uczelni A."""
    user = baker.make("bpp.BppUser", is_staff=True, is_active=True)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)
    return user


@pytest.fixture
def jednostka_b(uczelnia, uczelnia2):
    return baker.make(Jednostka, uczelnia=uczelnia2, nazwa="Jednostka B", skrot="JB")


@pytest.fixture
def rekord_uczelni_b(rekord, jednostka_b):
    """Praca wyłącznie uczelni B — autor w jednostce uczelni B."""
    rekord.dodaj_autora(baker.make(Autor, imiona="Ewa", nazwisko="Obca"), jednostka_b)
    return rekord


def test_redaktor_uczelni_a_nie_wzbogaca_pracy_uczelni_b(
    client, redaktor, rekord_uczelni_b
):
    r = rekord_uczelni_b
    wybor = _w(r)["strony"].wartosc_wyboru

    assert client.get(_url(r)).status_code == 404
    assert client.get(_url(r, "pbn")).status_code == 404
    assert client.post(_url(r), {"zrodlo_id": ZID, "pole": [wybor]}).status_code == 404
    assert client.post(_url(r), {"odswiez": "1"}).status_code == 404
    assert client.post(_url(r, nazwa="wzbogac_autorzy")).status_code == 404
    r.refresh_from_db()
    assert r.strony == "1-2"
    assert not ImportSession.objects.exists()


def test_sesja_autorow_nie_dopisze_do_pracy_uczelni_b(
    client, redaktor, rekord_uczelni_b, uczelnia, jednostka
):
    """Sesja otwarta, gdy praca była jeszcze „niczyja”; przy potwierdzaniu
    należy już wyłącznie do uczelni B."""
    from importer_publikacji.models import ImportedAuthor

    sesja = dodawanie_autorow.utworz_sesje(
        redaktor,
        uczelnia,
        rekord_uczelni_b,
        "CrossRef",
        DOI,
        [{"family": "Nowak"}],
        "/",
    )
    sesja.authors.update(
        matched_autor=baker.make(Autor, imiona="Anna", nazwisko="Nowak"),
        matched_jednostka=jednostka,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
    )

    res = client.post(
        reverse("importer_publikacji:authors-confirm", kwargs={"session_id": sesja.pk}),
        HTTP_HX_REQUEST="true",
    )

    assert "nie należy do Twojej uczelni" in res.content.decode()
    assert rekord_uczelni_b.autorzy_set.count() == 1


def test_praca_wlasnej_uczelni_i_praca_bez_autorow_sa_dostepne(
    client, redaktor, rekord, jednostka, uczelnia2
):
    # Bez autorów — nie należy jeszcze do nikogo.
    assert client.get(_url(rekord)).status_code == 200
    rekord.dodaj_autora(baker.make(Autor, imiona="Jan", nazwisko="Swój"), jednostka)
    assert client.get(_url(rekord)).status_code == 200


def test_superuzytkownik_widzi_prace_kazdej_uczelni(admin_client, rekord_uczelni_b):
    assert admin_client.get(_url(rekord_uczelni_b)).status_code == 200


# --- 2. Zmiana DOI między podglądem a zatwierdzeniem ------------------------


def test_zmiana_doi_od_podgladu_odrzuca_zapis(admin_client, rekord, crossref):
    """Inny redaktor zmienił DOI rekordu (strony zostały): wybór z podglądu
    dotyczy pracy spod POPRZEDNIEGO DOI — do rekordu nie trafia nic."""
    wybor = _w(rekord)["strony"].wartosc_wyboru
    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(doi="10.9999/inna.praca")

    res = admin_client.post(
        _url(rekord), {"zrodlo_id": ZID, "pole": [wybor]}, follow=True
    )

    assert "Nic nie zmieniono" in res.content.decode()
    rekord.refresh_from_db()
    assert rekord.strony == "1-2"
    assert not LogEntry.objects.filter(object_id=str(rekord.pk)).exists()


def test_podglad_niesie_identyfikator_zrodla(admin_client, rekord):
    assert f'name="zrodlo_id" value="{ZID}"' in (
        admin_client.get(_url(rekord)).content.decode()
    )


# --- 3. Zapis tylko zaznaczonych pól ----------------------------------------


def test_zapis_nie_rusza_niezaznaczonych_pol(admin_client, rekord):
    """Starszy rekord z adresem o niedozwolonym schemacie: pełny zapis
    wyczyściłby adres przy okazji przenoszenia samych stron."""
    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(
        www="mailto:ktos@example.com", public_www="mailto:inny@example.com"
    )
    rekord.refresh_from_db()
    wybor = _w(rekord)["strony"].wartosc_wyboru

    admin_client.post(_url(rekord), {"zrodlo_id": ZID, "pole": [wybor]})

    rekord.refresh_from_db()
    assert rekord.strony == "100-110"
    assert rekord.www == "mailto:ktos@example.com"
    assert rekord.public_www == "mailto:inny@example.com"


def test_same_relacje_nie_zapisuja_wiersza_rekordu(admin_client, rekord, denorms):
    """Przeniesienie samych słów kluczowych: adresy zostają, a rekord dostaje
    wpis w historii, nową datę zmiany i odświeżony opis."""
    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(
        www="mailto:ktos@example.com"
    )
    rekord.refresh_from_db()
    przed = rekord.ostatnio_zmieniony
    wybor = _w(rekord)["slowa_kluczowe"].wartosc_wyboru

    admin_client.post(_url(rekord), {"zrodlo_id": ZID, "pole": [wybor]})

    rekord.refresh_from_db()
    assert rekord.www == "mailto:ktos@example.com"
    assert list(rekord.slowa_kluczowe.names()) == ["Computer Science"]
    assert rekord.ostatnio_zmieniony > przed
    wersja = Version.objects.get_for_object(rekord).first()
    assert wersja.revision.comment == "Wzbogacono z CrossRef: pola Słowa kluczowe"


def test_czesciowy_zapis_odswieza_opis_bibliograficzny(admin_client, rekord, denorms):
    wybor = _w(rekord)["tytul_oryginalny"].wartosc_wyboru

    admin_client.post(_url(rekord), {"zrodlo_id": ZID, "pole": [wybor]})
    denorms.flush()

    rekord.refresh_from_db()
    assert rekord.tytul_oryginalny == "Test Publication Title"
    assert "Test Publication Title" in rekord.opis_bibliograficzny_cache
    assert rekord.tytul_oryginalny_sort == "test publication title"


# --- 5. Autorzy: sprzeczne identyfikatory i różne imiona --------------------


def _z_autorem(rekord, jednostka, imiona, nazwisko, **kw):
    autor = baker.make(Autor, imiona=imiona, nazwisko=nazwisko, **kw)
    rekord.dodaj_autora(autor, jednostka)
    return autor


def _statusy(rekord, osoby):
    return [w.status for w in porownaj_autorow(rekord, osoby).wiersze]


def test_inny_orcid_wyklucza_dopasowanie_po_inicjale(rekord, jednostka):
    """W BPP Jan Kowalski, źródło podaje Jerzego Kowalskiego z innym ORCID —
    to dwie osoby; Jerzy jest brakujący i trafia do kreatora."""
    _z_autorem(rekord, jednostka, "Jan", "Kowalski", orcid="0000-0001-1111-1111")
    osoba = {"family": "Kowalski", "given": "J.", "orcid": "0000-0002-2222-2222"}

    wynik = porownaj_autorow(rekord, [osoba])

    assert [w.status for w in wynik.wiersze] == [BRAK_W_BPP, TYLKO_W_BPP]
    assert wynik.osoby_brakujace == [osoba]


def test_rozne_pelne_imiona_wykluczaja_dopasowanie(rekord, jednostka):
    _z_autorem(rekord, jednostka, "Jan", "Kowalski")

    assert _statusy(rekord, [{"family": "Kowalski", "given": "Jerzy"}]) == [
        BRAK_W_BPP,
        TYLKO_W_BPP,
    ]
    # Ten sam inicjał bez pełnego imienia i to samo imię — ta sama osoba.
    assert _statusy(rekord, [{"family": "Kowalski", "given": "J."}]) == [ZGODNY]
    assert _statusy(rekord, [{"family": "Kowalski", "given": "Jan Maria"}]) == [ZGODNY]


def test_kilku_kandydatow_po_nazwisku_to_do_sprawdzenia(rekord, jednostka):
    _z_autorem(rekord, jednostka, "Jan", "Kowalski")
    _z_autorem(rekord, jednostka, "Jerzy", "Kowalski")

    wynik = porownaj_autorow(rekord, [{"family": "Kowalski", "given": "J."}])

    assert [w.status for w in wynik.wiersze] == [DO_SPRAWDZENIA, TYLKO_W_BPP]
    assert wynik.do_sprawdzenia == 1
    assert wynik.sa_roznice
    # Osoba „do sprawdzenia” nie trafia do kreatora jako brakująca.
    assert wynik.osoby_brakujace == []


# --- 7. Adres tylko w polu wolnego dostępu ----------------------------------


def test_adres_tylko_w_wolnym_dostepie_gdy_zrodlo_nie_ma_adresu(rekord, crossref):
    del crossref["resource"]
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    rekord.www = ""
    rekord.public_www = "https://repozytorium.example/praca"
    rekord.save()

    w = _w(rekord)["www"]

    assert w.status == BRAK_W_ZRODLE
    assert w.bpp == "https://repozytorium.example/praca"


# --- 8. Odpowiedź błędu CrossRef --------------------------------------------


@pytest.mark.parametrize("status", [429, 503])
def test_blad_http_crossref_nie_daje_500(admin_client, rekord, mocker, status):
    """CrossRef odpowiada błędem z poprawnym JSON-em bez ``message`` —
    zostają dane z pamięci podręcznej i komunikat, nie awaria strony."""
    odpowiedz = mocker.Mock(status_code=status, headers={}, content=b"{}")
    odpowiedz.json.return_value = {"status": "error"}
    mocker.patch("crossref.restful.HTTPRequest.do_http_request", return_value=odpowiedz)

    res = admin_client.post(_url(rekord), {"odswiez": "1"}, follow=True)

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "Nie udało się pobrać danych z CrossRef" in tresc
    assert "Pokazuję dane pobrane wcześniej" in tresc
    assert CrossrefAPICache.objects.get(doi=DOI).data["page"] == "100-110"


# --- 9. Encje HTML w tytułach ------------------------------------------------


def test_encje_html_nie_sa_roznica(rekord, crossref):
    assert reguly.tekst("Badania &amp; rozwój") == reguly.tekst("Badania & rozwój")
    crossref["title"] = ["Badania &amp; rozw&oacute;j"]
    CrossrefAPICache.objects.filter(doi=DOI).update(data=crossref)
    rekord.tytul_oryginalny = "Badania & rozwój"
    rekord.save()

    assert _w(rekord)["tytul_oryginalny"].status == ZGODNE
