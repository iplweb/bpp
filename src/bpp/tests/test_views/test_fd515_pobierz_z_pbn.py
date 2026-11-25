"""FD#515 — jeden przycisk „Pobierz z PBN” przy polu „Odpowiednik w PBN”.

Redaktor nie wybiera, według czego szukać: system próbuje kolejno DOI,
adresów WWW i ISBN. Testy bez sieci — serwer PBN zastępuje atrapa.
"""

import json

import pytest
from django.urls import reverse
from django.utils.html import escapejs
from model_bakery import baker

from bpp.models import Uczelnia
from bpp.views.api.pbn_odpowiednik import (
    BRAK,
    DO_WYBORU,
    KOMUNIKAT_AUTORYZACJA,
    PEWNY,
    PUSTE,
    PobierzOdpowiednikPublikacjiView,
    znajdz_odpowiednik_publikacji,
)
from fixtures.pbn_api import pbn_general_json
from pbn_api.exceptions import WillNotExportError
from pbn_api.models import Journal, Publication, Publisher

UID_1 = "6accb7c13d7d997e0c94d1a1"
UID_2 = "6accb7c13d7d997e0c94d1a2"
DOI = "10.5555/FD515.Test"
WWW = "https://czasopismo.example.org/artykul/42"
ISBN = "9780128195178"
TYTUL = "Wpływ testów na jakość oprogramowania"


def _publikacja(uid=UID_1, **obiekt):
    obiekt.setdefault("title", TYTUL)
    obiekt.setdefault("year", 2024)
    obiekt.setdefault("type", "ARTICLE")
    status = obiekt.pop("status", "ACTIVE")
    return Publication.objects.create(
        mongoId=uid,
        status=status,
        verificationLevel="x",
        verified=True,
        versions=[{"current": True, "object": obiekt}],
    )


# --- wspólna logika ----------------------------------------------------------


@pytest.mark.django_db
def test_po_doi_lokalnie_bez_wzgledu_na_wielkosc_liter():
    _publikacja(doi=DOI)

    wynik = znajdz_odpowiednik_publikacji(
        doi=DOI.lower(), tytul="zupełnie inny", rodzaj="ARTICLE"
    )

    assert wynik.status == PEWNY
    assert wynik.uid == UID_1
    assert wynik.po_czym.startswith("DOI ")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "adres",
    [
        WWW,
        "http://czasopismo.example.org/artykul/42/",
        "czasopismo.example.org/artykul/42",
        "HTTPS://Czasopismo.Example.ORG/artykul/42",
    ],
)
def test_praca_bez_doi_z_adresem_www_zgodnym_z_pbn(adres):
    """Kryterium ze zgłoszenia: praca bez DOI, ale z adresem WWW zgodnym
    z PBN, dostaje odpowiednik."""
    _publikacja(publicUri=WWW)

    wynik = znajdz_odpowiednik_publikacji(
        www=adres, tytul=TYTUL.upper() + "!", rodzaj="ARTICLE"
    )

    assert wynik.status == PEWNY, wynik
    assert wynik.uid == UID_1
    assert wynik.po_czym.startswith("adres WWW ")


@pytest.mark.django_db
def test_publiczny_adres_www_tez_jest_sprawdzany():
    _publikacja(publicUri=WWW)

    wynik = znajdz_odpowiednik_publikacji(
        www="https://inny.example.org/a/1",
        public_www=WWW,
        tytul=TYTUL,
        rodzaj="ARTICLE",
    )

    assert wynik.status == PEWNY
    assert len(wynik.sprawdzono) == 2


@pytest.mark.django_db
def test_adres_www_o_innym_tytule_nie_jest_pewny():
    """Adres WWW bywa wspólny (książka i jej rozdziały) — przy innym tytule
    rekord jest tylko propozycją do wyboru."""
    _publikacja(publicUri=WWW, title="Cała książka")

    wynik = znajdz_odpowiednik_publikacji(www=WWW, tytul=TYTUL)

    assert wynik.status == DO_WYBORU
    assert wynik.uidy == [UID_1]
    assert wynik.uid is None


@pytest.mark.django_db
def test_sam_adres_domeny_nie_jest_identyfikatorem():
    _publikacja(publicUri="https://wydawnictwo.example.org")

    wynik = znajdz_odpowiednik_publikacji(
        www="https://wydawnictwo.example.org/", tytul=TYTUL
    )

    assert wynik.status == PUSTE


@pytest.mark.django_db
def test_isbn_ksiazki_i_rozdzialu_wybiera_rekord_o_tym_samym_tytule():
    _publikacja(UID_1, isbn=ISBN, title="Cała książka", type="BOOK")
    _publikacja(UID_2, title=TYTUL, type="CHAPTER", book={"isbn": ISBN})

    rozdzial = znajdz_odpowiednik_publikacji(
        isbn="978-0-12-819517-8", tytul=TYTUL, rodzaj="CHAPTER"
    )
    nieznany = znajdz_odpowiednik_publikacji(
        isbn=ISBN, tytul="Inny rozdział", rodzaj="CHAPTER"
    )

    assert (rozdzial.status, rozdzial.uid) == (PEWNY, UID_2)
    assert nieznany.status == DO_WYBORU
    assert set(nieznany.uidy) == {UID_1, UID_2}


@pytest.mark.django_db
def test_e_isbn_jest_sprawdzany_gdy_isbn_nie_dal_wyniku():
    _publikacja(isbn=ISBN, type="BOOK")

    wynik = znajdz_odpowiednik_publikacji(
        isbn="9788374307338", e_isbn=ISBN, tytul=TYTUL, rodzaj="BOOK"
    )

    assert wynik.status == PEWNY
    assert len(wynik.sprawdzono) == 2


@pytest.mark.django_db
def test_kolejny_identyfikator_rozstrzyga_niejednoznaczny_wczesniejszy():
    """DOI zdublowany w PBN, ale adres WWW wskazuje jeden rekord."""
    _publikacja(UID_1, doi=DOI, title="Wersja pierwsza")
    _publikacja(UID_2, doi=DOI, publicUri=WWW)

    wynik = znajdz_odpowiednik_publikacji(
        doi=DOI, www=WWW, tytul=TYTUL, rodzaj="ARTICLE"
    )

    assert (wynik.status, wynik.uid) == (PEWNY, UID_2)


@pytest.mark.django_db
def test_puste_pola_i_brak_wyniku_daja_czytelne_komunikaty():
    puste = znajdz_odpowiednik_publikacji(tytul=TYTUL)
    brak = znajdz_odpowiednik_publikacji(doi=DOI, www=WWW, isbn=ISBN)

    assert puste.status == PUSTE
    assert "Uzupełnij DOI" in puste.komunikat
    assert brak.status == BRAK
    assert "Nie udało się znaleźć odpowiednika w PBN" in brak.komunikat
    for fragment in (DOI, "czasopismo.example.org/artykul/42", ISBN):
        assert fragment in brak.komunikat


@pytest.mark.django_db
def test_bez_tokena_pbn_szukamy_tylko_lokalnie():
    def klient():
        raise WillNotExportError("brak tokena")

    wynik = znajdz_odpowiednik_publikacji(doi=DOI, klient=klient)

    assert wynik.status == BRAK
    assert wynik.bez_serwera == KOMUNIKAT_AUTORYZACJA


@pytest.mark.django_db
def test_doi_szukany_na_serwerze_pbn_gdy_brak_w_kopii(mocker, pbn_uczelnia, pbn_client):
    rekord = pbn_general_json(
        {"type": "ARTICLE", "title": TYTUL, "year": 2024, "doi": DOI}, mongoId=UID_1
    )
    zapytania = []

    def szukaj(**kw):
        zapytania.append(kw)
        return [{"mongoId": UID_1}] if kw.get("doi") else []

    mocker.patch.object(pbn_client, "search_publications", side_effect=szukaj)
    pbn_client.transport.return_values[f"/api/v1/publications/id/{UID_1}"] = rekord

    wynik = znajdz_odpowiednik_publikacji(
        doi=DOI, rodzaj="ARTICLE", klient=lambda: pbn_client
    )

    assert (wynik.status, wynik.uid) == (PEWNY, UID_1)
    assert zapytania and "doi" in zapytania[0]
    # Rekord trafił do lokalnej kopii — pole formularza umie go pokazać.
    assert Publication.objects.filter(pk=UID_1).exists()


@pytest.mark.django_db
def test_lokalne_trafienie_nie_dotyka_serwera_pbn():
    _publikacja(doi=DOI)

    def klient():
        raise AssertionError("nie powinno być zapytania do serwera PBN")

    wynik = znajdz_odpowiednik_publikacji(doi=DOI, rodzaj="ARTICLE", klient=klient)
    assert wynik.status == PEWNY


# --- widoki ------------------------------------------------------------------


def _post(klient_http, widok, **dane):
    odp = klient_http.post(reverse(f"bpp:{widok}"), data=dane)
    assert odp.status_code == 200, odp.status_code
    return json.loads(odp.content)


@pytest.mark.django_db
def test_widok_publikacji_zwraca_pewny_odpowiednik(admin_client, uczelnia):
    _publikacja(publicUri=WWW)

    res = _post(
        admin_client,
        "api_get_pbn_by_identifiers",
        www=WWW,
        tytul_oryginalny=TYTUL,
        model="ciagle",
    )

    assert res["status"] == PEWNY
    assert res["id"] == UID_1
    assert res["kandydaci"][0]["etykieta"]
    assert "adres WWW" in res["komunikat"]


@pytest.mark.django_db
def test_widok_publikacji_niczego_nie_wiaze(admin_client, uczelnia, wydawnictwo_ciagle):
    _publikacja(doi=DOI)
    wydawnictwo_ciagle.doi = DOI
    wydawnictwo_ciagle.save()

    res = _post(admin_client, "api_get_pbn_by_identifiers", doi=DOI, model="ciagle")

    assert res["id"] == UID_1
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.pbn_uid_id is None


@pytest.mark.django_db
def test_widok_publikacji_puste_pola(admin_client, uczelnia):
    res = _post(admin_client, "api_get_pbn_by_identifiers", tytul_oryginalny=TYTUL)

    assert res["status"] == PUSTE
    assert "id" not in res
    assert "Uzupełnij" in res["komunikat"]


@pytest.mark.django_db
def test_widok_bez_tokena_pbn_dopisuje_uwage(rf, admin_user, uczelnia):
    """Brak autoryzacji w PBN nie jest błędem — jest wynik z lokalnej kopii
    i podpowiedź, jak przeszukać także serwer PBN."""
    uczelnia.pbn_client = lambda *a, **kw: (_ for _ in ()).throw(
        WillNotExportError("brak tokena")
    )
    req = rf.post("/", data={"doi": DOI})
    req.user = admin_user
    req._uczelnia = uczelnia

    res = json.loads(PobierzOdpowiednikPublikacjiView.as_view()(req).content)

    assert res["status"] == BRAK
    assert res["uwaga"] == KOMUNIKAT_AUTORYZACJA


@pytest.mark.django_db
def test_widoki_tylko_dla_zalogowanych_redaktorow(client, normal_django_user):
    url = reverse("bpp:api_get_pbn_by_identifiers")

    assert client.post(url, data={"doi": DOI}).status_code == 302
    client.force_login(normal_django_user)
    assert client.post(url, data={"doi": DOI}).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "widok",
    [
        "api_get_pbn_by_identifiers",
        "api_pobierz_z_pbn_autora",
        "api_pobierz_z_pbn_zrodla",
        "api_pobierz_z_pbn_wydawcy",
    ],
)
def test_widoki_wymagaja_uprawnienia_do_zmiany_rekordu(client, staff_user, widok):
    """Sam dostęp do panelu (``is_staff``) nie wystarcza — potrzebne jest
    to samo uprawnienie, którego panel wymaga do zmiany danego rekordu."""
    staff_user.user_permissions.clear()
    staff_user.groups.clear()
    client.force_login(staff_user)

    odp = client.post(reverse(f"bpp:{widok}"), data={"doi": DOI, "nazwa": "x"})

    assert odp.status_code == 403


@pytest.mark.django_db
def test_widok_zrodla_po_issn_i_wykaz_ministerialny_pierwszy(admin_client, uczelnia):
    def journal(uid, **obiekt):
        return Journal.objects.create(
            mongoId=uid,
            status="ACTIVE",
            verificationLevel="x",
            verified=True,
            versions=[{"current": True, "object": obiekt}],
        )

    journal(UID_1, title="Acta Testologica", issn="1234-5678")

    jeden = _post(admin_client, "api_pobierz_z_pbn_zrodla", issn="1234-5678")
    assert (jeden["status"], jeden["id"]) == (PEWNY, UID_1)

    journal(UID_2, title="Acta Testologica (druk)", eissn="1234-5678", mniswId=77)
    kilka = _post(admin_client, "api_pobierz_z_pbn_zrodla", issn="1234-5678")
    assert kilka["status"] == DO_WYBORU
    assert [k["id"] for k in kilka["kandydaci"]] == [UID_2, UID_1]
    assert "id" not in kilka

    assert _post(admin_client, "api_pobierz_z_pbn_zrodla")["status"] == PUSTE
    assert _post(admin_client, "api_pobierz_z_pbn_zrodla", nazwa="Nic")["status"] == (
        BRAK
    )


@pytest.mark.django_db
def test_widok_wydawcy_po_nazwie(admin_client, uczelnia):
    Publisher.objects.create(
        mongoId=UID_1,
        status="ACTIVE",
        verificationLevel="x",
        verified=True,
        versions=[{"current": True, "object": {"publisherName": "Wydawnictwo ABC"}}],
    )

    res = _post(admin_client, "api_pobierz_z_pbn_wydawcy", nazwa="wydawnictwo abc")

    assert (res["status"], res["id"]) == (PEWNY, UID_1)


# --- formularze: jeden przycisk zamiast dwóch --------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model, endpoint",
    [
        ("wydawnictwo_ciagle", "api_get_pbn_by_identifiers"),
        ("wydawnictwo_zwarte", "api_get_pbn_by_identifiers"),
        ("autor", "api_pobierz_z_pbn_autora"),
        ("zrodlo", "api_pobierz_z_pbn_zrodla"),
        ("wydawca", "api_pobierz_z_pbn_wydawcy"),
    ],
)
def test_formularz_ma_jeden_przycisk_pobierz_z_pbn(admin_client, model, endpoint):
    baker.make(Uczelnia)

    html = admin_client.get(reverse(f"admin:bpp_{model}_add")).content.decode()

    assert "id_pobierz_z_pbn" in html
    assert "Pobierz z PBN" in html
    assert escapejs(reverse(f"bpp:{endpoint}")) in html
    assert "Pobierz po DOI" not in html
    assert "Pobierz po ISBN" not in html
    # Reguła widoczności i komunikaty przy przycisku zamiast alert().
    assert "przycisk.hide()" in html
    assert "id_pobierz_z_pbn_komunikat" in html


# --- recenzja PR 1184: automat tylko przy dowodzie bez sprzeczności ----------


@pytest.mark.django_db
def test_rozdzial_z_doi_ksiazki_nie_dostaje_rekordu_ksiazki():
    """Rozdział ma w BPP wpisany DOI książki, a w kopii PBN jest tylko
    książka — pojedyncze trafienie po DOI nie może być „pewne”."""
    _publikacja(doi=DOI, title="Cała książka", type="BOOK")

    wynik = znajdz_odpowiednik_publikacji(doi=DOI, tytul=TYTUL, rodzaj="CHAPTER")

    assert wynik.status == DO_WYBORU
    assert wynik.uidy == [UID_1]


@pytest.mark.django_db
@pytest.mark.parametrize("identyfikator", ["doi", "isbn"])
def test_rozdzial_zatytulowany_jak_tom_nie_dostaje_rekordu_ksiazki(identyfikator):
    """Ten sam tytuł i ten sam ISBN/DOI, ale w PBN to KSIĄŻKA, a w BPP
    rozdział — zgodny tytuł nie wystarcza."""
    _publikacja(doi=DOI, isbn=ISBN, type="BOOK")

    wynik = znajdz_odpowiednik_publikacji(
        **{identyfikator: DOI if identyfikator == "doi" else ISBN},
        tytul=TYTUL,
        rodzaj="CHAPTER",
    )

    assert wynik.status == DO_WYBORU
    assert wynik.uid is None


@pytest.mark.django_db
@pytest.mark.parametrize("rodzaj, typ_pbn", [("", "ARTICLE"), ("ARTICLE", None)])
def test_nieustalony_rodzaj_po_ktorejkolwiek_stronie_to_reczny_wybor(rodzaj, typ_pbn):
    obiekt = {"doi": DOI}
    if typ_pbn is None:
        obiekt["type"] = ""
    _publikacja(**obiekt)

    wynik = znajdz_odpowiednik_publikacji(doi=DOI, tytul=TYTUL, rodzaj=rodzaj)

    assert wynik.status == DO_WYBORU


@pytest.mark.django_db
@pytest.mark.parametrize("pole", ["doi", "isbn", "www"])
def test_rekord_usuniety_w_pbn_nie_jest_kandydatem(pole):
    _publikacja(doi=DOI, isbn=ISBN, publicUri=WWW, status="DELETED")

    wynik = znajdz_odpowiednik_publikacji(
        **{pole: {"doi": DOI, "isbn": ISBN, "www": WWW}[pole]},
        tytul=TYTUL,
        rodzaj="ARTICLE",
    )

    assert wynik.status == BRAK
    assert wynik.uidy == []


@pytest.mark.django_db
def test_rekord_usuniety_w_pbn_pobrany_z_serwera_jest_odrzucany(
    mocker, pbn_uczelnia, pbn_client
):
    rekord = pbn_general_json(
        {"type": "ARTICLE", "title": TYTUL, "year": 2024, "doi": DOI},
        mongoId=UID_1,
        status="DELETED",
    )
    mocker.patch.object(
        pbn_client, "search_publications", return_value=[{"mongoId": UID_1}]
    )
    pbn_client.transport.return_values[f"/api/v1/publications/id/{UID_1}"] = rekord

    wynik = znajdz_odpowiednik_publikacji(
        doi=DOI, tytul=TYTUL, rodzaj="ARTICLE", klient=lambda: pbn_client
    )

    assert wynik.status == BRAK


@pytest.mark.django_db
def test_wiecej_niz_10_trafien_nie_gubi_rekordu_o_zgodnym_tytule():
    """Książka z 25 rozdziałami o tym samym ISBN: właściwy rozdział musi
    zostać znaleziony, choć lista do pokazania ma najwyżej 10 pozycji."""
    for i in range(25):
        _publikacja(
            f"6accb7c13d7d997e0c94{i:04d}",
            title=f"Rozdział {i}",
            type="CHAPTER",
            book={"isbn": ISBN},
        )
    # Właściwy rekord ma klucz sortujący się NA KOŃCU.
    _publikacja("ffffb7c13d7d997e0c94ffff", type="CHAPTER", book={"isbn": ISBN})

    pewny = znajdz_odpowiednik_publikacji(isbn=ISBN, tytul=TYTUL, rodzaj="CHAPTER")
    lista = znajdz_odpowiednik_publikacji(isbn=ISBN, tytul=TYTUL, rodzaj="")

    assert (pewny.status, pewny.uid) == (PEWNY, "ffffb7c13d7d997e0c94ffff")
    # Bez automatu rekord o zgodnym tytule jest pierwszy na obciętej liście.
    assert lista.status == DO_WYBORU
    assert len(lista.uidy) == 10
    assert lista.uidy[0] == "ffffb7c13d7d997e0c94ffff"


@pytest.mark.django_db
def test_lokalne_rozdzialy_nie_zaslaniaja_ksiazki_na_serwerze(
    mocker, pbn_uczelnia, pbn_client
):
    """W kopii są tylko rozdziały z ISBN-em książki; szukamy książki —
    brak zgodnego tytułu lokalnie oznacza pytanie do serwera PBN."""
    _publikacja(UID_2, title="Rozdział", type="CHAPTER", book={"isbn": ISBN})
    ksiazka = pbn_general_json(
        {"type": "BOOK", "title": TYTUL, "year": 2024, "isbn": ISBN}, mongoId=UID_1
    )
    szukaj = mocker.patch.object(
        pbn_client, "search_publications", return_value=[{"mongoId": UID_1}]
    )
    pbn_client.transport.return_values[f"/api/v1/publications/id/{UID_1}"] = ksiazka

    wynik = znajdz_odpowiednik_publikacji(
        isbn=ISBN, tytul=TYTUL, rodzaj="BOOK", klient=lambda: pbn_client
    )

    szukaj.assert_called()
    assert (wynik.status, wynik.uid) == (PEWNY, UID_1)


@pytest.mark.django_db
def test_niedostepny_pbn_jedna_proba_i_wynik_z_lokalnej_kopii(
    mocker, admin_client, admin_user, uczelnia
):
    """Przycisk nie wisi minutami: jedna próba z krótkim czasem oczekiwania,
    bez pętli ponowień, a redaktor dostaje wynik z kopii i uwagę."""
    import requests

    from bpp.views.api.pbn_odpowiednik import KOMUNIKAT_NIEDOSTEPNY, TIMEOUT_PBN

    uczelnia.pbn_app_name = "x"
    uczelnia.pbn_app_token = "y"
    uczelnia.pbn_api_root = "https://pbn.invalid"
    type(uczelnia).objects.filter(pk=uczelnia.pk).update(
        pbn_app_name="x", pbn_app_token="y", pbn_api_root="https://pbn.invalid"
    )
    admin_user.pbn_token = "tok"
    admin_user.save()
    proby = []

    def padnij(*a, **kw):
        proby.append(kw.get("timeout"))
        raise requests.ConnectionError("down")

    mocker.patch("requests.get", side_effect=padnij)
    mocker.patch("requests.post", side_effect=padnij)
    sen = mocker.patch("pbn_client.transport.time.sleep")
    zgloszenie = mocker.patch("bpp.views.api.pbn_odpowiednik.capture_exception")

    res = _post(admin_client, "api_get_pbn_by_identifiers", doi=DOI, model="ciagle")

    assert len(proby) == 1, proby
    assert proby[0] == TIMEOUT_PBN
    sen.assert_not_called()
    zgloszenie.assert_not_called()
    assert res["status"] == BRAK
    assert res["uwaga"] == KOMUNIKAT_NIEDOSTEPNY


# --- podpowiedź: automat zatrzymał się tylko na nieustalonym rodzaju ---------


@pytest.mark.django_db
def test_podpowiedz_gdy_brakuje_tylko_charakteru_formalnego(admin_client, uczelnia):
    """Nowe wydawnictwo zwarte bez wybranego charakteru: rekord znaleziony
    po DOI nie jest wstawiany sam, a redaktor dowiaduje się dlaczego
    i co zrobić."""
    from bpp.views.api.pbn_odpowiednik import (
        PODPOWIEDZ_INNY_CHARAKTER,
        PODPOWIEDZ_WYBIERZ_CHARAKTER,
    )

    _publikacja(doi=DOI, type="BOOK")
    inny = baker.make("bpp.Charakter_Formalny", charakter_ogolny="xxx")
    ksiazka = baker.make("bpp.Charakter_Formalny", charakter_ogolny="ksi")

    bez = _post(admin_client, "api_get_pbn_by_identifiers", doi=DOI)
    z_innym = _post(
        admin_client, "api_get_pbn_by_identifiers", doi=DOI, charakter_formalny=inny.pk
    )
    z_ksiazka = _post(
        admin_client,
        "api_get_pbn_by_identifiers",
        doi=DOI,
        charakter_formalny=ksiazka.pk,
    )

    assert bez["status"] == DO_WYBORU
    assert bez["podpowiedz"] == PODPOWIEDZ_WYBIERZ_CHARAKTER
    assert "Charakter formalny" in bez["podpowiedz"]
    assert z_innym["status"] == DO_WYBORU
    assert z_innym["podpowiedz"] == PODPOWIEDZ_INNY_CHARAKTER
    # Po wybraniu charakteru rekord wstawia się sam — bez podpowiedzi.
    assert (z_ksiazka["status"], z_ksiazka["id"]) == (PEWNY, UID_1)
    assert "podpowiedz" not in z_ksiazka


@pytest.mark.django_db
def test_bez_podpowiedzi_gdy_wybor_jest_reczny_z_innego_powodu(admin_client, uczelnia):
    """Kilka rekordów albo inny tytuł — wybranie charakteru nic by nie dało,
    więc nie obiecujemy tego redaktorowi."""
    _publikacja(UID_1, isbn=ISBN, title="Rozdział A", type="CHAPTER")
    _publikacja(UID_2, isbn=ISBN, title="Rozdział B", type="CHAPTER")

    kilka = _post(
        admin_client, "api_get_pbn_by_identifiers", isbn=ISBN, tytul_oryginalny="Inny"
    )
    sprzeczny = _post(
        admin_client,
        "api_get_pbn_by_identifiers",
        isbn=ISBN,
        tytul_oryginalny="Rozdział A",
        model="ciagle",
    )

    assert kilka["status"] == DO_WYBORU and "podpowiedz" not in kilka
    assert sprzeczny["status"] == DO_WYBORU and "podpowiedz" not in sprzeczny
