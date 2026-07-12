import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_TWARDY


@pytest.mark.django_db
def test_porownaj_z_baza_wykrywa_roznice_emaila():
    # Stopień/stanowisko porównujemy SEMANTYCZNIE po FK (skrót w pliku „kpt." vs
    # nazwa w bazie „kapitan" dałyby fałszywe „różne"). Plan 3 rozwiązuje wartość
    # z pliku do FK na wierszu: row.stopien / row.stanowisko_dydaktyczne.
    stopien = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    stanow = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    stanow_prof = baker.make(
        "bpp.StanowiskoDydaktyczne", nazwa="profesor", skrot="prof."
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(
        Autor,
        nazwisko="Kowalski",
        imiona="Jan",
        email="stary@example.com",
        stopien_sluzbowy=stopien,
    )
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, stanowisko=stanow
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        stopien=stopien,  # plik → ten sam FK co w bazie (kpt.)
        stanowisko_dydaktyczne=stanow_prof,  # plik → inny FK niż baza (ad.)
        dane_znormalizowane={
            "email": "nowy@example.com",  # różni się od bazy
            "stopień_służbowy": "kpt.",  # zgodny skrótem (ten sam FK)
            "stanowisko_dydaktyczne": "prof.",  # różni się (inny FK)
        },
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["email"] == {
        "plik": "nowy@example.com",
        "baza": "stary@example.com",
        "rozne": True,
    }
    # zgodny stopień podany skrótem NIE daje różnicy (ten sam FK):
    assert wynik["stopien"]["rozne"] is False
    assert wynik["stanowisko"]["rozne"] is True
    assert wynik["stanowisko"]["plik"] == "prof."


@pytest.mark.django_db
def test_porownaj_z_baza_bez_autora_daje_puste_baza():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        confidence="brak",
        zmiany_potrzebne=False,
        dane_znormalizowane={"email": "x@example.com"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 2},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["email"] == {"plik": "x@example.com", "baza": "", "rozne": False}


@pytest.mark.django_db
def test_tabela_podgladu_renderuje_kolumny_porownania(admin_client, admin_user):
    stanow = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan", email="baza@example.com")
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, stanowisko=stanow
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
        finished_successfully=True,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=False,
        dane_znormalizowane={
            "email": "plik@example.com",
            "stanowisko_dydaktyczne": "adiunkt",
        },
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    # nagłówki nowych kolumn
    assert "E-mail (plik → baza)" in tresc
    assert "Stopień służbowy" in tresc
    assert "Stanowisko dydaktyczne" in tresc
    # różnica e-maila podświetlona + obie wartości widoczne
    assert "import-porownanie-rozne" in tresc
    assert "plik@example.com" in tresc
    assert "baza@example.com" in tresc


def test_porownaj_z_baza_tytul_rozny(db):
    from model_bakery import baker

    from import_pracownikow.models import ImportPracownikowRow

    # nazwa/skrot celowo różne od danych bazowych (baseline.sql seeduje
    # "doktor"/"dr" i "profesor"/"prof." — kolizja unique=True bez tego).
    dr = baker.make("bpp.Tytul", nazwa="doktor testowy 1", skrot="dr-t1")
    prof = baker.make("bpp.Tytul", nazwa="profesor testowy 1", skrot="prof-t1")
    autor = baker.make("bpp.Autor", tytul=prof)
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    p = row.porownaj_z_baza()["tytul"]
    assert p["rozne"] is True
    assert p["plik"] == "dr"


def test_porownaj_z_baza_tytul_bez_autora_nie_rozny(db):
    from model_bakery import baker

    from import_pracownikow.models import ImportPracownikowRow

    # nazwa/skrot celowo różne od danych bazowych (kolizja z baseline.sql,
    # patrz komentarz w teście wyżej).
    dr = baker.make("bpp.Tytul", nazwa="doktor testowy 2", skrot="dr-t2")
    row = baker.make(
        ImportPracownikowRow,
        autor=None,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    assert row.porownaj_z_baza()["tytul"]["rozne"] is False


def test_porownaj_z_baza_funkcja_rozna(db):
    from model_bakery import baker

    from import_pracownikow.models import ImportPracownikowRow

    # nazwa celowo różna od danych bazowych (baseline.sql seeduje "asystent"
    # i "adiunkt" — kolizja unique=True bez tego).
    stara = baker.make("bpp.Funkcja_Autora", nazwa="asystent testowy 1")
    nowa = baker.make("bpp.Funkcja_Autora", nazwa="adiunkt testowy 1")
    aj = baker.make("bpp.Autor_Jednostka", funkcja=stara)
    row = baker.make(
        ImportPracownikowRow,
        autor=aj.autor,
        autor_jednostka=aj,
        funkcja_autora=nowa,
        dane_znormalizowane={"stanowisko": "adiunkt"},
    )
    assert row.porownaj_z_baza()["funkcja"]["rozne"] is True
