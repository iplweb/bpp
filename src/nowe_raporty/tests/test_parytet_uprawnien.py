"""Testy seedu domyślnych uprawnień DefinicjaRaportu.

Pola Uczelnia.pokazuj_raport_* zostały usunięte — seed bierze domyślne
uprawnienia ze stałej ``DEFAULTY_FLAG`` (mapuje dawne defaulty pól). Te testy
pilnują, że nowy deploy dostaje raporty z poprawnymi domyślnymi poziomami
dostępu/aktywnością.
"""

import pytest
from model_bakery import baker

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.seeding import seed_default_reports


@pytest.mark.django_db
@pytest.mark.parametrize(
    "slug,poziom_dostepu,aktywny,wymaga_grupy",
    [
        # raport-autorow: dawny default POKAZUJ_ZAWSZE -> WSZYSCY, bez grupy.
        ("raport-autorow", DefinicjaRaportu.DOSTEP_WSZYSCY, True, False),
        # jednostki/wydzialy: POKAZUJ_ZALOGOWANYM -> ZALOGOWANI + grupa raporty.
        ("raport-jednostek", DefinicjaRaportu.DOSTEP_ZALOGOWANI, True, True),
        ("raport-wydzialow", DefinicjaRaportu.DOSTEP_ZALOGOWANI, True, True),
        # raport-uczelni: dawny default POKAZUJ_NIGDY -> nieaktywny.
        ("raport-uczelni", DefinicjaRaportu.DOSTEP_ZALOGOWANI, False, False),
    ],
)
def test_seed_domyslne_uprawnienia(slug, poziom_dostepu, aktywny, wymaga_grupy):
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug=slug)

    assert definicja.poziom_dostepu == poziom_dostepu
    assert definicja.aktywny is aktywny

    nazwy_grup = set(definicja.wymagane_grupy.values_list("name", flat=True))
    if wymaga_grupy:
        assert GR_RAPORTY_WYSWIETLANIE in nazwy_grup
    else:
        assert nazwy_grup == set()


@pytest.mark.django_db
def test_seed_tworzy_definicje_dla_czterech_raportow():
    seed_default_reports()
    slugi = set(DefinicjaRaportu.objects.values_list("slug", flat=True))
    assert slugi == {
        "raport-autorow",
        "raport-jednostek",
        "raport-wydzialow",
        "raport-uczelni",
    }


@pytest.mark.django_db
def test_seed_definicje_idempotentny():
    seed_default_reports()
    seed_default_reports()
    assert DefinicjaRaportu.objects.filter(slug="raport-autorow").count() == 1


@pytest.mark.django_db
def test_seed_nie_nadpisuje_istniejacej_definicji():
    # Redaktor zmienil uprawnienia w adminie -> seed nie moze tego deptac.
    report = baker.make("flexible_reports.Report", slug="raport-autorow")
    istn = DefinicjaRaportu.objects.create(
        nazwa="MOJA",
        slug="raport-autorow",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=report,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_SUPERUSER,
    )
    seed_default_reports()
    istn.refresh_from_db()
    assert istn.nazwa == "MOJA"
    assert istn.poziom_dostepu == DefinicjaRaportu.DOSTEP_SUPERUSER


@pytest.mark.django_db
def test_seed_kolejnosc_uczelnia_wydzial_jednostka_autor():
    seed_default_reports()
    kolejnosc = {d.slug: d.kolejnosc for d in DefinicjaRaportu.objects.all()}
    assert kolejnosc["raport-uczelni"] < kolejnosc["raport-wydzialow"]
    assert kolejnosc["raport-wydzialow"] < kolejnosc["raport-jednostek"]
    assert kolejnosc["raport-jednostek"] < kolejnosc["raport-autorow"]
