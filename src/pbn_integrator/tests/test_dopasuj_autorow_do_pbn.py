"""FD#510: komenda ``dopasuj_autorow_do_pbn`` — dopasowanie istniejących
autorów bez odpowiednika w PBN do osób z PBN."""

import csv

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.core.management import CommandError, call_command
from model_bakery import baker
from openpyxl import load_workbook
from reversion.models import Version

from bpp.models import Autor
from pbn_api.models import OsobaZInstytucji, Publication, Scientist
from pbn_integrator.utils.dopasowanie_autorow import (
    MOZLIWY_DUPLIKAT,
    PEWNE,
    PRAWDOPODOBNE,
    SPRZECZNE,
    imiona_zgodne,
    warianty_nazwiska,
    zbadaj_autorow,
)

OSOBA_1 = "5e709189878c28a04737dc61"
OSOBA_2 = "5e709189878c28a04737dc62"
ORCID = "0000-0002-1825-0097"


def _osoba(pk, nazwisko, imiona, *, orcid=None, z_instytucji=False, status=""):
    obiekt = {"lastName": nazwisko, "name": imiona}
    if orcid:
        obiekt["orcid"] = orcid
    osoba = baker.make(
        Scientist,
        mongoId=pk,
        status=status,
        versions=[{"current": True, "object": obiekt}],
    )
    if z_instytucji:
        baker.make(
            OsobaZInstytucji, personId=osoba, firstName=imiona, lastName=nazwisko
        )
    return osoba


_licznik = iter(range(1, 10_000))


def _praca_w_pbn(wydawnictwo_ciagle_maker, jednostka, autor, osoby, *, rok=2023):
    """Praca BPP z odpowiednikiem w PBN; ``osoby`` to autorzy z kopii
    publikacji PBN: {identyfikator: (nazwisko, imiona)}."""
    n = next(_licznik)
    publikacja = baker.make(
        Publication,
        mongoId=f"{n:024x}",
        versions=[
            {
                "current": True,
                "object": {
                    "title": f"Praca {n}",
                    "authors": {
                        pk: {"lastName": nazwisko, "name": imiona}
                        for pk, (nazwisko, imiona) in osoby.items()
                    },
                    "orderList": {"AUTHOR": list(osoby)},
                },
            }
        ],
    )
    praca = wydawnictwo_ciagle_maker(
        tytul_oryginalny=f"Praca {n}", rok=rok, pbn_uid=publikacja
    )
    praca.dodaj_autora(autor, jednostka)
    return praca


@pytest.fixture
def wydawnictwo_ciagle_maker(
    db, jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    def maker(**kw):
        return baker.make("bpp.Wydawnictwo_Ciagle", **kw)

    return maker


def _uruchom(tmp_path, *argumenty):
    raport = tmp_path / "raport.csv"
    call_command("dopasuj_autorow_do_pbn", "--raport", str(raport), *argumenty)
    with raport.open(encoding="utf-8-sig", newline="") as plik:
        return {int(w["ID autora"]): w for w in csv.DictReader(plik, delimiter=";")}


def test_warianty_nazwiska_i_imion():
    assert warianty_nazwiska("Kowalska-Nowak", "Wójcik, Zając") == {
        "kowalska-nowak",
        "kowalska",
        "nowak",
        "wojcik",
        "zajac",
    }
    assert imiona_zgodne("Jan Maria", "Jan")
    assert not imiona_zgodne("Jan", "J.")
    assert imiona_zgodne("Jan", "J.", inicjal=True)
    assert not imiona_zgodne("Jan", "Janusz")


@pytest.mark.django_db
def test_dry_run_niczego_nie_zapisuje(tmp_path, uczelnia):
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", orcid=ORCID)

    wiersze = _uruchom(tmp_path)

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert not LogEntry.objects.filter(object_id=str(autor.pk)).exists()
    assert wiersze[autor.pk]["Poziom pewności"] == PEWNE
    assert wiersze[autor.pk]["Proponowany PBN UID"] == OSOBA_1
    assert wiersze[autor.pk]["Zapisano"] == "nie"


@pytest.mark.django_db
def test_dry_run_i_zapisz_wykluczaja_sie(tmp_path, uczelnia):
    with pytest.raises(CommandError):
        _uruchom(tmp_path, "--dry-run", "--zapisz")


@pytest.mark.django_db
def test_dopasowanie_po_orcid_z_wpisem_w_historii(tmp_path, uczelnia, admin_user):
    _osoba(OSOBA_1, "Kowalska-Nowak", "Anna", orcid=ORCID)
    autor = baker.make(Autor, nazwisko="Kowalska", imiona="Anna", orcid=ORCID)

    wiersze = _uruchom(tmp_path, "--zapisz", "--uzytkownik", admin_user.username)

    autor.refresh_from_db()
    assert autor.pbn_uid_id == OSOBA_1
    assert wiersze[autor.pk]["Zapisano"] == "tak"
    wpis = LogEntry.objects.get(content_type__model="autor", object_id=str(autor.pk))
    assert wpis.action_flag == CHANGE
    assert wpis.user == admin_user
    assert OSOBA_1 in wpis.change_message
    assert "ORCID" in wpis.change_message
    # Wersja sprzed zmiany i po niej — zmianę da się cofnąć z „Historii”.
    assert Version.objects.get_for_object(autor).count() == 2


@pytest.mark.django_db
def test_samo_nazwisko_to_tylko_prawdopodobne(tmp_path, uczelnia):
    _osoba(OSOBA_1, "Wiśniewska", "Halina", z_instytucji=True)
    autor = baker.make(Autor, nazwisko="Wiśniewska", imiona="Halina Maria")

    wiersze = _uruchom(tmp_path, "--zapisz")

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Poziom pewności"] == PRAWDOPODOBNE
    assert wiersze[autor.pk]["Proponowany PBN UID"] == OSOBA_1


@pytest.mark.django_db
def test_poprzednie_nazwisko_i_publikacje_daja_pewnosc(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    """„Po autorach” (poprzednie nazwisko wśród osób z instytucji)
    i „po publikacjach” wskazują tę samą osobę — to wystarcza do zapisu."""
    _osoba(OSOBA_1, "Wójcik", "Maria", z_instytucji=True)
    autor = baker.make(
        Autor, nazwisko="Zamężna", imiona="Maria", poprzednie_nazwiska="Wójcik"
    )
    _praca_w_pbn(
        wydawnictwo_ciagle_maker,
        jednostka,
        autor,
        {OSOBA_2: ("Inny", "Autor"), OSOBA_1: ("Wójcik", "M.")},
    )

    wiersze = _uruchom(tmp_path, "--zapisz")

    autor.refresh_from_db()
    assert autor.pbn_uid_id == OSOBA_1
    assert wiersze[autor.pk]["Poziom pewności"] == PEWNE
    assert "publikacje" in wiersze[autor.pk]["Źródła dowodu"]
    assert wiersze[autor.pk]["Liczba zgodnych prac"] == "1"


@pytest.mark.django_db
def test_same_publikacje_prawdopodobne_chyba_ze_prog(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    _osoba(OSOBA_1, "Smith", "John")
    autor = baker.make(Autor, nazwisko="Smith", imiona="John")
    for _ in range(3):
        _praca_w_pbn(
            wydawnictwo_ciagle_maker, jednostka, autor, {OSOBA_1: ("Smith", "John")}
        )

    wiersze = _uruchom(tmp_path, "--zapisz")
    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Poziom pewności"] == PRAWDOPODOBNE
    assert wiersze[autor.pk]["Liczba zgodnych prac"] == "3"

    wiersze = _uruchom(tmp_path, "--zapisz", "--pewne-od-prac", "3")
    autor.refresh_from_db()
    assert autor.pbn_uid_id == OSOBA_1
    assert wiersze[autor.pk]["Zapisano"] == "tak"


@pytest.mark.django_db
def test_sprzeczne_zrodla_brak_zapisu(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    """ORCID wskazuje jedną osobę, publikacje — inną."""
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    _osoba(OSOBA_2, "Kowalski", "Jan")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", orcid=ORCID)
    _praca_w_pbn(
        wydawnictwo_ciagle_maker, jednostka, autor, {OSOBA_2: ("Kowalski", "Jan")}
    )

    wiersze = _uruchom(tmp_path, "--zapisz")

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Poziom pewności"] == SPRZECZNE
    assert wiersze[autor.pk]["Zapisano"] == "nie"


@pytest.mark.django_db
def test_publikacje_wskazuja_rozne_osoby_sprzeczne(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    _osoba(OSOBA_1, "Kowalski", "Jan")
    _osoba(OSOBA_2, "Kowalski", "Jan")
    for osoba in (OSOBA_1, OSOBA_2):
        _praca_w_pbn(
            wydawnictwo_ciagle_maker, jednostka, autor, {osoba: ("Kowalski", "Jan")}
        )

    wiersze = _uruchom(tmp_path, "--zapisz", "--pewne-od-prac", "1")

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Poziom pewności"] == SPRZECZNE


@pytest.mark.django_db
def test_osoba_przypieta_do_innego_autora_brak_zapisu(tmp_path, uczelnia):
    osoba = _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    inny = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid=osoba)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="J.", orcid=ORCID)

    wiersze = _uruchom(tmp_path, "--zapisz")

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Poziom pewności"] == MOZLIWY_DUPLIKAT
    assert f"ID {inny.pk}" in wiersze[autor.pk]["Uwagi"]
    # Autor z odpowiednikiem w ogóle nie jest badany.
    assert inny.pk not in wiersze


@pytest.mark.django_db
def test_dwoch_autorow_wskazuje_te_sama_osobe_brak_zapisu(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    _osoba(OSOBA_1, "Wiśniewska", "Halina", z_instytucji=True)
    autorzy = [
        baker.make(Autor, nazwisko="Wiśniewska", imiona="Halina") for _ in range(2)
    ]
    for autor in autorzy:
        _praca_w_pbn(
            wydawnictwo_ciagle_maker,
            jednostka,
            autor,
            {OSOBA_1: ("Wiśniewska", "Halina")},
        )

    wiersze = _uruchom(tmp_path, "--zapisz")

    for autor in autorzy:
        autor.refresh_from_db()
        assert autor.pbn_uid_id is None
        assert wiersze[autor.pk]["Poziom pewności"] == MOZLIWY_DUPLIKAT


@pytest.mark.django_db
def test_istniejacy_pbn_uid_nietkniety(tmp_path, uczelnia):
    """Autor z odpowiednikiem nie jest badany, nawet gdy ORCID wskazuje
    inną osobę."""
    stara = _osoba(OSOBA_1, "Kowalski", "Jan")
    _osoba(OSOBA_2, "Kowalski", "Jan", orcid=ORCID)
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", orcid=ORCID, pbn_uid=stara
    )

    wiersze = _uruchom(tmp_path, "--zapisz")

    autor.refresh_from_db()
    assert autor.pbn_uid_id == OSOBA_1
    assert wiersze == {}
    assert not LogEntry.objects.filter(object_id=str(autor.pk)).exists()


@pytest.mark.django_db
def test_osoba_usunieta_w_pbn_nie_jest_proponowana(tmp_path, uczelnia):
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID, status="DELETED")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", orcid=ORCID)

    wiersze = _uruchom(tmp_path, "--zapisz")

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Proponowany PBN UID"] == ""


@pytest.mark.django_db
def test_osoba_z_publikacji_nieobecna_lokalnie_nie_jest_zapisywana(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    autor = baker.make(Autor, nazwisko="Smith", imiona="John")
    _praca_w_pbn(
        wydawnictwo_ciagle_maker, jednostka, autor, {OSOBA_1: ("Smith", "John")}
    )

    wiersze = _uruchom(tmp_path, "--zapisz", "--pewne-od-prac", "1")

    autor.refresh_from_db()
    assert autor.pbn_uid_id is None
    assert wiersze[autor.pk]["Poziom pewności"] == PRAWDOPODOBNE
    assert "lokalnej kopii" in wiersze[autor.pk]["Uwagi"]


@pytest.mark.django_db
def test_imiennicy_w_publikacji_rozstrzyga_kolejnosc(
    jednostka, wydawnictwo_ciagle_maker
):
    """Dwie osoby o tym samym nazwisku i inicjale w jednej pracy —
    rozstrzyga pozycja na liście autorów."""
    _osoba(OSOBA_1, "Nowak", "Jan")
    _osoba(OSOBA_2, "Nowak", "Jerzy")
    autor = baker.make(Autor, nazwisko="Nowak", imiona="J.")
    praca = _praca_w_pbn(
        wydawnictwo_ciagle_maker,
        jednostka,
        baker.make(Autor, nazwisko="Nowak", imiona="Jan", pbn_uid_id=OSOBA_1),
        {OSOBA_1: ("Nowak", "Jan"), OSOBA_2: ("Nowak", "Jerzy")},
    )
    praca.dodaj_autora(autor, jednostka)  # kolejność 1 → druga osoba

    (propozycja,) = zbadaj_autorow([autor])

    assert propozycja.scientist_id == OSOBA_2


@pytest.mark.django_db
def test_zawezenie_lata_i_limit(
    tmp_path, uczelnia, jednostka, wydawnictwo_ciagle_maker
):
    stary = baker.make(Autor, nazwisko="Aaa", imiona="Stary")
    nowy = baker.make(Autor, nazwisko="Bbb", imiona="Nowy")
    bez_prac = baker.make(Autor, nazwisko="Ccc", imiona="Bez")
    _praca_w_pbn(wydawnictwo_ciagle_maker, jednostka, stary, {}, rok=2015)
    _praca_w_pbn(wydawnictwo_ciagle_maker, jednostka, nowy, {}, rok=2023)

    assert set(_uruchom(tmp_path, "--rok-od", "2022", "--rok-do", "2025")) == {nowy.pk}
    assert set(_uruchom(tmp_path, "--limit", "1")) == {stary.pk}
    assert set(_uruchom(tmp_path)) == {stary.pk, nowy.pk, bez_prac.pk}


@pytest.mark.django_db
def test_wiele_uczelni_wymaga_wskazania(tmp_path, uczelnia):
    baker.make("bpp.Uczelnia")

    with pytest.raises(CommandError, match="--uczelnia"):
        _uruchom(tmp_path)


@pytest.mark.django_db
def test_wiele_uczelni_zaweza_autorow_i_osoby(tmp_path, uczelnia, jednostka):
    """W instalacji z wieloma uczelniami badani są autorzy danej uczelni,
    a po nazwisku szukamy tylko wśród osób z JEJ instytucji PBN."""
    instytucja = baker.make("pbn_api.Institution")
    uczelnia.pbn_uid = instytucja
    uczelnia.save()
    druga = baker.make("bpp.Uczelnia")
    obca_jednostka = baker.make("bpp.Jednostka", uczelnia=druga)

    osoba = _osoba(OSOBA_1, "Wiśniewska", "Halina")
    baker.make(
        OsobaZInstytucji,
        personId=osoba,
        firstName="Halina",
        lastName="Wiśniewska",
        institutionId=baker.make("pbn_api.Institution"),
    )
    nasz = baker.make(Autor, nazwisko="Wiśniewska", imiona="Halina")
    nasz.dodaj_jednostke(jednostka)
    cudzy = baker.make(Autor, nazwisko="Cudzy", imiona="Autor")
    cudzy.dodaj_jednostke(obca_jednostka)

    wiersze = _uruchom(tmp_path, "--uczelnia", str(uczelnia.pk))

    assert set(wiersze) == {nasz.pk}
    # Osoba pracuje w INNEJ instytucji — nie jest kandydatem.
    assert wiersze[nasz.pk]["Proponowany PBN UID"] == ""


@pytest.mark.django_db
def test_raport_xlsx(tmp_path, uczelnia):
    _osoba(OSOBA_1, "Kowalski", "Jan", orcid=ORCID)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", orcid=ORCID)
    raport = tmp_path / "raport.xlsx"

    call_command("dopasuj_autorow_do_pbn", "--raport", str(raport))

    arkusz = load_workbook(raport).active
    wiersze = list(arkusz.iter_rows(values_only=True))
    assert wiersze[0][0] == "ID autora"
    assert wiersze[1][0] == autor.pk
    assert wiersze[1][5] == PEWNE
    assert wiersze[1][7] == "Kowalski Jan"


@pytest.mark.django_db
def test_zly_format_raportu(tmp_path, uczelnia):
    with pytest.raises(CommandError, match="xlsx"):
        call_command("dopasuj_autorow_do_pbn", "--raport", str(tmp_path / "r.txt"))
