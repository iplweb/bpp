"""FD#527: ``punkty_mnisw`` / ``typ_mnisw`` jako aliasy tylko do odczytu
na rekordach i publikacjach — dla szablonów trzymanych w bazie. Pola modeli
i kolumny nazywają się po staremu."""

from decimal import Decimal

import pytest
from django.core.exceptions import FieldError
from django.template import Context, Template
from model_bakery import baker

from bpp.models import (
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Rekord,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.cache import RekordView

MODELE = [
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Patent,
    Rekord,
    RekordView,
]

SZABLON = Template(
    "{{ praca.punkty_mnisw }}|{{ praca.typ_mnisw }}|{{ praca.typ_mnisw.nazwa }}"
    "|{{ praca.typ_mnisw.skrot }}"
)
SZABLON_STARY = Template(
    "{{ praca.punkty_kbn }}|{{ praca.typ_kbn }}|{{ praca.typ_kbn.nazwa }}"
    "|{{ praca.typ_kbn.skrot }}"
)


@pytest.fixture
def praca(db, jezyki, charaktery_formalne, statusy_korekt):
    typ = baker.make(Typ_KBN, nazwa="Typ A", skrot="TA")
    return baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="FD527 alias",
        punkty_kbn=Decimal("140"),
        typ_kbn=typ,
    )


@pytest.mark.parametrize("model", MODELE)
def test_fd527_modele_maja_aliasy_bez_nowych_pol(model):
    assert hasattr(model, "punkty_mnisw")
    # Patent nie ma typu MNiSW/MEiN — ani pod dawną, ani pod nową nazwą.
    assert hasattr(model, "typ_mnisw") == hasattr(model, "typ_kbn")
    assert hasattr(model, "typ_mnisw") == (model is not Patent)
    # Strażnik: alias to nie pole — baza i migracje go nie widzą.
    nazwy_pol = {pole.name for pole in model._meta.get_fields()}
    assert "punkty_kbn" in nazwy_pol
    assert not {"punkty_mnisw", "typ_mnisw"} & nazwy_pol


def test_fd527_szablon_na_publikacji_i_rekordzie(praca):
    praca.refresh_from_db()
    rekord = Rekord.objects.get_for_model(praca)
    for obiekt in (praca, rekord):
        nowe = SZABLON.render(Context({"praca": obiekt}))
        assert nowe == SZABLON_STARY.render(Context({"praca": obiekt}))
        assert nowe.startswith("140")
        assert nowe.endswith("|Typ A|Typ A|TA")
        assert obiekt.punkty_mnisw == obiekt.punkty_kbn == Decimal("140")
        assert obiekt.typ_mnisw == obiekt.typ_kbn


def test_fd527_patent_bez_typu_nie_wywraca_szablonu(db, patent):
    # Patent nie ma typu MNiSW/MEiN — alias, jak dawna nazwa, daje pustkę.
    assert not hasattr(patent, "typ_mnisw")
    wynik = SZABLON.render(Context({"praca": patent}))
    assert wynik == SZABLON_STARY.render(Context({"praca": patent}))


def test_fd527_alias_jest_tylko_do_odczytu(praca):
    praca.refresh_from_db()
    with pytest.raises(AttributeError):
        praca.punkty_mnisw = 5
    with pytest.raises(AttributeError):
        praca.typ_mnisw = None
    with pytest.raises(TypeError):
        Wydawnictwo_Ciagle(punkty_mnisw=5)
    praca.refresh_from_db()
    assert praca.punkty_kbn == Decimal("140")


def test_fd527_sortowanie_rekordow_po_aliasie(praca):
    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="FD527 alias niska",
        punkty_kbn=Decimal("20"),
        typ_kbn=praca.typ_kbn,
    )
    qs = Rekord.objects.filter(tytul_oryginalny__startswith="FD527 alias")
    for alias, pole in (
        ("punkty_mnisw", "punkty_kbn"),
        ("-punkty_mnisw", "-punkty_kbn"),
        ("typ_mnisw__nazwa", "typ_kbn__nazwa"),
    ):
        nowe = list(qs.order_by(alias, "pk").values_list("pk", flat=True))
        assert nowe == list(qs.order_by(pole, "pk").values_list("pk", flat=True))
    assert [r.punkty_kbn for r in qs.order_by("-punkty_mnisw")] == [140, 20]


def test_fd527_ograniczenie_alias_nie_jest_polem_orm(praca):
    """Udokumentowane ograniczenie: alias działa w szablonach, w sortowaniu
    rekordów i w językach zapytań — ale filtr ORM go nie zna, a sortowanie
    po aliasie jest tylko na ``Rekord`` (to on jest bazą raportów)."""
    with pytest.raises(FieldError):
        Rekord.objects.filter(punkty_mnisw=140).count()
    with pytest.raises(FieldError):
        list(Wydawnictwo_Ciagle.objects.order_by("punkty_mnisw"))
