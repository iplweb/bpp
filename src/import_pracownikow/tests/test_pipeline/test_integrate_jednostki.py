"""Integracja importu pracowników — FAZA 0: rozstrzyganie decyzji o jednostkach
(utwórz / auto / mapuj / pomiń), tworzenie brakujących i podłączanie wierszy."""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia, Wydzial
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowRow,
)
from import_pracownikow.pewnosc import STATUS_BRAK
from import_pracownikow.pipeline.integrate import integruj

AKCEPTUJ = ImportPracownikowJednostka.DECYZJA_AKCEPTUJ
MAPUJ = ImportPracownikowJednostka.DECYZJA_MAPUJ
POMIN = ImportPracownikowJednostka.DECYZJA_POMIN
BRAK = ImportPracownikowJednostka.TRYB_BRAK
ZGADYWANIE = ImportPracownikowJednostka.TRYB_ZGADYWANIE


@pytest.fixture
def uczelnia(uczelnia):
    """Utwardza precondycję „dokładnie jedna uczelnia" (ambient-data/xdist).

    ``_rozstrzygnij_jednostki`` woła ``get_single_uczelnia_or_none()``, które
    zwraca ``None`` gdy w bazie jest 0 LUB >1 uczelnia — wtedy tryb BRAK NIE
    tworzy jednostki (``dec.utworzona`` zostaje ``None``). Baseline ma 0 uczelni,
    więc solo fixture daje dokładnie 1 i testy przechodzą. Pod xdist/pytest-split
    sąsiedni test może jednak zostawić zacommitowaną DRUGĄ uczelnię (ambient-data)
    → ``get_single_uczelnia_or_none()`` degraduje do ``None`` i te testy flakują
    (zielone w izolacji, czerwone w niektórych układach shardów). Kasujemy
    ambient-nadmiar, aby fixture'owa uczelnia była jedyna (rollback testu i tak
    przywraca stan)."""
    Uczelnia.objects.exclude(pk=uczelnia.pk).delete()
    return uczelnia


def _imp():
    return baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)


def _decyzja(imp, nazwa, *, tryb=BRAK, decyzja=AKCEPTUJ, skrot="", **kw):
    return baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa=nazwa,
        tryb=tryb,
        decyzja=decyzja,
        skrot_sugerowany=skrot,
        **kw,
    )


def _wiersz(imp, dec, *, autor=None, **kw):
    return ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=None,
        zrodlo_jednostki=dec,
        jednostka_status=dec.tryb,
        zmiany_potrzebne=False,
        diff_do_utworzenia={},
        **kw,
    )


@pytest.mark.django_db
def test_tworzy_jednostke_brak_i_podlacza_wszystkie_wiersze(uczelnia):
    imp = _imp()
    dec = _decyzja(imp, "Zakład Transfuzjologii", skrot="ZT")
    r1, r2 = _wiersz(imp, dec), _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))

    dec.refresh_from_db()
    assert dec.utworzona is not None
    assert dec.utworzona.nazwa == "Zakład Transfuzjologii"
    assert dec.utworzona.skrot == "ZT"
    assert dec.utworzona.uczelnia_id == uczelnia.pk
    for r in (r1, r2):
        r.refresh_from_db()
        assert r.jednostka_id == dec.utworzona_id


@pytest.mark.django_db
def test_zgadywanie_uzywa_auto_nie_tworzy_nowej(uczelnia):
    j = baker.make(Jednostka, nazwa="Zakład Istniejący", skrot="ZI", uczelnia=uczelnia)
    imp = _imp()
    dec = _decyzja(imp, "Zaklad Istniejacy", tryb=ZGADYWANIE, auto_jednostka=j)
    r = _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))

    r.refresh_from_db()
    assert r.jednostka_id == j.pk
    assert not Jednostka.objects.filter(nazwa="Zaklad Istniejacy").exists()


@pytest.mark.django_db
def test_mapuj_uzywa_wybranej(uczelnia):
    j = baker.make(Jednostka, nazwa="Docelowa", skrot="DOC", uczelnia=uczelnia)
    imp = _imp()
    dec = _decyzja(imp, "Zrodlowa", decyzja=MAPUJ, wybrana_jednostka=j)
    r = _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))

    r.refresh_from_db()
    assert r.jednostka_id == j.pk
    assert not Jednostka.objects.filter(nazwa="Zrodlowa").exists()


@pytest.mark.django_db
def test_pomin_zostawia_wiersze_niedopasowane(uczelnia):
    imp = _imp()
    dec = _decyzja(imp, "Pomijana", decyzja=POMIN)
    r = _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))

    r.refresh_from_db()
    assert r.jednostka_id is None
    assert not Jednostka.objects.filter(nazwa="Pomijana").exists()


@pytest.mark.django_db
def test_uzywaj_wydzialow_tworzy_wydzial_domyslny_i_podpina(uczelnia):
    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()
    imp = _imp()
    dec = _decyzja(imp, "Zakład Pod Wydziałem", skrot="ZPW")
    _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))

    dec.refresh_from_db()
    assert dec.utworzona.parent_id is not None  # pod węzłem-wydziałem, nie root
    assert Wydzial.objects.filter(nazwa__istartswith="Wydział Domyślny").exists()


@pytest.mark.django_db
def test_root_gdy_uczelnia_bez_wydzialow(uczelnia):
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()
    imp = _imp()
    dec = _decyzja(imp, "Zakład Rootowy", skrot="ZR")
    _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))

    dec.refresh_from_db()
    assert dec.utworzona.parent_id is None


@pytest.mark.django_db
def test_idempotentna_drugi_przebieg_nie_duplikuje(uczelnia):
    imp = _imp()
    dec = _decyzja(imp, "Jednorazowa", skrot="JZ")
    _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))
    dec.refresh_from_db()
    utworzona_pk = dec.utworzona_id
    assert utworzona_pk is not None

    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    imp.save(update_fields=["stan"])
    integruj(imp, MockProgress(imp))

    dec.refresh_from_db()
    assert dec.utworzona_id == utworzona_pk
    assert Jednostka.objects.filter(nazwa="Jednorazowa").count() == 1


@pytest.mark.django_db
def test_pomin_plus_utworz_nowego_autora_nie_crashuje(uczelnia):
    imp = _imp()
    dec = _decyzja(imp, "Pomijana", decyzja=POMIN)
    row = _wiersz(
        imp,
        dec,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane={"nazwisko": "Testowy", "imię": "Jan"},
    )

    # bez guardu jednostka__isnull=False → get_or_create(jednostka_id=None) →
    # IntegrityError wywala cały task; z guardem wiersz jest pominięty.
    integruj(imp, MockProgress(imp))

    row.refresh_from_db()
    assert row.jednostka_id is None
    assert row.autor_id is None  # autora nie tworzymy bez jednostki


@pytest.mark.django_db
def test_bez_jednoznacznej_uczelni_degraduje_bez_crasha():
    baker.make(Uczelnia)
    baker.make(Uczelnia)  # >1 → get_single_uczelnia_or_none() = None
    imp = _imp()
    dec = _decyzja(imp, "Zaklad Bez Uczelni", skrot="ZBU")
    r = _wiersz(imp, dec)

    integruj(imp, MockProgress(imp))  # nie rzuca

    r.refresh_from_db()
    assert r.jednostka_id is None
    assert not Jednostka.objects.filter(nazwa="Zaklad Bez Uczelni").exists()
