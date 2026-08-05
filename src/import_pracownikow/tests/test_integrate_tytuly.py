"""Integracja importu pracowników — FAZA 0.5: rozstrzyganie decyzji o tytułach
(utwórz / auto / mapuj / pomiń), tworzenie brakujących i podłączanie wierszy.

Mirror ``test_pipeline/test_integrate_jednostki.py``. ``Tytul`` jest seedowany w
baseline, więc dla „nowych" tytułów używamy stringów spoza baseline (nazwy/skróty
z dopiskami testowymi), a dla „istniejących"/mapuj tworzymy własne przez baker.
"""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowTytul,
)
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_WIELU
from import_pracownikow.pipeline.integrate import _rozstrzygnij_tytuly, integruj

AKCEPTUJ = ImportPracownikowTytul.DECYZJA_AKCEPTUJ
MAPUJ = ImportPracownikowTytul.DECYZJA_MAPUJ
POMIN = ImportPracownikowTytul.DECYZJA_POMIN
BRAK = ImportPracownikowTytul.TRYB_BRAK
ZGADYWANIE = ImportPracownikowTytul.TRYB_ZGADYWANIE


def _imp():
    return baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)


def _decyzja(imp, nazwa, *, tryb=BRAK, decyzja=AKCEPTUJ, **kw):
    return baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa=nazwa,
        tryb=tryb,
        decyzja=decyzja,
        **kw,
    )


def _wiersz(imp, dec, *, autor=None, **kw):
    return ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        tytul=None,
        zrodlo_tytulu=dec,
        tytul_status=dec.tryb,
        zmiany_potrzebne=False,
        diff_do_utworzenia={},
        **kw,
    )


@pytest.mark.django_db
def test_tworzy_tytul_brak_i_podlacza_wszystkie_wiersze():
    imp = _imp()
    dec = _decyzja(
        imp,
        "Tytuł Testowy Galaktyczny",
        nazwa_do_utworzenia="Tytuł Testowy Galaktyczny",
        skrot_do_utworzenia="TTG",
    )
    r1, r2 = _wiersz(imp, dec), _wiersz(imp, dec)

    utworzono = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono == 1
    dec.refresh_from_db()
    assert dec.utworzony is not None
    assert dec.utworzony.nazwa == "Tytuł Testowy Galaktyczny"
    assert dec.utworzony.skrot == "TTG"
    for r in (r1, r2):
        r.refresh_from_db()
        assert r.tytul_id == dec.utworzony_id


@pytest.mark.django_db
def test_skrot_unikalny_przy_kolizji_z_istniejacym():
    baker.make(Tytul, nazwa="Inny Tytuł Zajmujący Skrót", skrot="ZAJ")
    imp = _imp()
    dec = _decyzja(
        imp,
        "Nowy Tytuł Do Utworzenia",
        nazwa_do_utworzenia="Nowy Tytuł Do Utworzenia",
        skrot_do_utworzenia="ZAJ",
    )
    r = _wiersz(imp, dec)

    _rozstrzygnij_tytuly(imp, MockProgress(imp))

    dec.refresh_from_db()
    assert dec.utworzony.nazwa == "Nowy Tytuł Do Utworzenia"
    assert dec.utworzony.skrot == "ZAJ2"  # sufiks numeryczny przy kolizji
    r.refresh_from_db()
    assert r.tytul_id == dec.utworzony_id


@pytest.mark.django_db
def test_skrot_z_zaproponuj_gdy_pusty_skrot_do_utworzenia():
    imp = _imp()
    # skrot_do_utworzenia pusty → baza skrótu z zaproponuj_skrot_tytulu(nazwa
    # źródłowa) = przycięta forma źródłowa.
    dec = _decyzja(
        imp,
        "prof. wizytujący testowy",
        nazwa_do_utworzenia="Profesor Wizytujący Testowy",
        skrot_do_utworzenia="",
    )
    _wiersz(imp, dec)

    _rozstrzygnij_tytuly(imp, MockProgress(imp))

    dec.refresh_from_db()
    assert dec.utworzony is not None
    assert dec.utworzony.skrot == "prof. wizytujący testowy"


@pytest.mark.django_db
def test_mapuj_uzywa_istniejacego():
    t = baker.make(Tytul, nazwa="Tytuł Docelowy Mapowany", skrot="TDM")
    imp = _imp()
    dec = _decyzja(imp, "Tytuł Źródłowy Do Mapowania", decyzja=MAPUJ, wybrany_tytul=t)
    r = _wiersz(imp, dec)

    utworzono = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono == 0
    r.refresh_from_db()
    assert r.tytul_id == t.pk
    assert not Tytul.objects.filter(nazwa="Tytuł Źródłowy Do Mapowania").exists()


@pytest.mark.django_db
def test_zgadywanie_uzywa_auto_nie_tworzy_nowego():
    t = baker.make(Tytul, nazwa="Tytuł Auto Dopasowany", skrot="TAD")
    imp = _imp()
    dec = _decyzja(imp, "Tytuł Auto Dopasowny", tryb=ZGADYWANIE, auto_tytul=t)
    r = _wiersz(imp, dec)

    utworzono = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono == 0
    r.refresh_from_db()
    assert r.tytul_id == t.pk
    assert not Tytul.objects.filter(nazwa="Tytuł Auto Dopasowny").exists()


@pytest.mark.django_db
def test_pomin_zostawia_wiersze_bez_tytulu():
    imp = _imp()
    dec = _decyzja(imp, "Tytuł Pomijany", decyzja=POMIN)
    r = _wiersz(imp, dec)

    utworzono = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono == 0
    r.refresh_from_db()
    assert r.tytul_id is None
    assert not Tytul.objects.filter(nazwa="Tytuł Pomijany").exists()


@pytest.mark.django_db
def test_pomin_nowy_autor_bez_tytulu(autor_jednostka_fixture):
    """``pomin`` → wiersz bez tytułu; nowy autor tworzony bez tytułu."""
    _, jednostka = autor_jednostka_fixture
    imp = _imp()
    dec = _decyzja(imp, "Tytuł Pomijany Autor", decyzja=POMIN)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka,
        zrodlo_tytulu=dec,
        tytul_status=dec.tryb,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane={"nazwisko": "Beztytułowy", "imię": "Jan"},
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )

    integruj(imp, MockProgress(imp))

    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.tytul_id is None


@pytest.mark.django_db
def test_pomin_istniejacy_autor_zachowuje_tytul():
    """``pomin`` NIE kasuje tytułu istniejącego, dopasowanego autora."""
    tytul = baker.make(Tytul, nazwa="Profesor Zachowany Testowy", skrot="ProfZach")
    autor = baker.make(Autor, nazwisko="Zachowany", imiona="Marek", tytul=tytul)
    jednostka = baker.make(Jednostka, nazwa="Jednostka Zachowana", skrot="JZach")
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    imp = _imp()
    dec = _decyzja(imp, "Tytuł Pomijany Istniejący", decyzja=POMIN)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        zrodlo_tytulu=dec,
        tytul_status=dec.tryb,
        dane_znormalizowane={"nazwisko": "Zachowany", "imię": "Marek"},
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )

    integruj(imp, MockProgress(imp))

    autor.refresh_from_db()
    assert autor.tytul_id == tytul.pk


@pytest.mark.django_db
def test_idempotentna_drugi_przebieg_nie_duplikuje():
    imp = _imp()
    dec = _decyzja(
        imp,
        "Tytuł Jednorazowy",
        nazwa_do_utworzenia="Tytuł Jednorazowy",
        skrot_do_utworzenia="TJ",
    )
    _wiersz(imp, dec)

    _rozstrzygnij_tytuly(imp, MockProgress(imp))
    dec.refresh_from_db()
    utworzony_pk = dec.utworzony_id
    assert utworzony_pk is not None

    utworzono2 = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono2 == 0  # guard `utworzony` — drugi przebieg nic nie tworzy
    dec.refresh_from_db()
    assert dec.utworzony_id == utworzony_pk
    assert Tytul.objects.filter(nazwa="Tytuł Jednorazowy").count() == 1


@pytest.mark.django_db
def test_wiersz_brak_autora_nie_crashuje_podlaczania():
    """BLOCKER-guard: wiersz z ``autor=None`` (i ``autor_jednostka=None``) mający
    ``zrodlo_tytulu`` NIE może wywołać ``check_if_integration_needed()``
    (``getattr`` na ``None``) — bez guardu ``AttributeError`` ubiłby cały task
    liveops. Z guardem ustawiamy tylko ``row.tytul`` (bez rechecku)."""
    tytul = baker.make(Tytul, nazwa="Tytuł Dla Braku Autora", skrot="TBA")
    imp = _imp()
    dec = _decyzja(imp, "Tytuł Braku Autora", tryb=ZGADYWANIE, auto_tytul=tytul)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        autor_jednostka=None,
        zrodlo_tytulu=dec,
        tytul_status=dec.tryb,
        confidence=STATUS_WIELU,
        dane_znormalizowane={"nazwisko": "Wielokrotny"},
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )

    # Bez guardu: check_if_integration_needed() → getattr(None, ...) →
    # AttributeError. Z guardem: tylko row.tytul.
    _rozstrzygnij_tytuly(imp, MockProgress(imp))

    row.refresh_from_db()
    assert row.tytul_id == tytul.pk
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_nazwa_edytowana_na_istniejaca_dolacza_nie_tworzy():
    """Edytowana ``nazwa_do_utworzenia`` == nazwa istniejącego ``Tytul`` (inna
    wielkość liter) → re-match po ``iexact`` dołącza, zamiast rzucić
    ``IntegrityError`` na ``Tytul.nazwa`` (``unique=True``)."""
    istn = baker.make(Tytul, nazwa="Tytuł Już Istnieje", skrot="TJIexact")
    imp = _imp()
    dec = _decyzja(
        imp,
        "Tytuł Źródłowy Zupełnie Inny",
        nazwa_do_utworzenia="tytuł już istnieje",
        skrot_do_utworzenia="INNYSKROT",
    )
    r = _wiersz(imp, dec)

    utworzono = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono == 0
    dec.refresh_from_db()
    assert dec.utworzony_id == istn.pk
    r.refresh_from_db()
    assert r.tytul_id == istn.pk
    assert Tytul.objects.filter(nazwa__iexact="tytuł już istnieje").count() == 1


@pytest.mark.django_db
def test_dwie_decyzje_ta_sama_nowa_nazwa_nie_koliduja():
    """Dwie decyzje z tą samą edytowaną ``nazwa_do_utworzenia`` — pierwsza tworzy,
    druga dołącza (re-match), bez ``IntegrityError`` na unikalnej nazwie."""
    imp = _imp()
    dec1 = _decyzja(
        imp,
        "Alfa źródło",
        nazwa_do_utworzenia="Wspólny Nowy Tytuł",
        skrot_do_utworzenia="WNT",
    )
    dec2 = _decyzja(
        imp,
        "Beta źródło",
        nazwa_do_utworzenia="Wspólny Nowy Tytuł",
        skrot_do_utworzenia="WNT",
    )
    r1, r2 = _wiersz(imp, dec1), _wiersz(imp, dec2)

    utworzono = _rozstrzygnij_tytuly(imp, MockProgress(imp))

    assert utworzono == 1  # tylko pierwsza (wg ordering nazwa_zrodlowa) tworzy
    assert Tytul.objects.filter(nazwa="Wspólny Nowy Tytuł").count() == 1
    r1.refresh_from_db()
    r2.refresh_from_db()
    assert r1.tytul_id == r2.tytul_id
