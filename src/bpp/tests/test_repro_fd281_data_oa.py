"""Freshdesk #281: data udostępnienia OA — pełna data ALBO miesiąc i rok.

Klient nie chce wpisywać zmyślonego dnia udostępnienia w otwartym dostępie.
Testy na produkcyjnym PBN (rekord 9067 na APOŻ) pokazały, że PBN przyjmuje
``releaseDate`` (pełna data) albo ``releaseDateMonth`` + ``releaseDateYear``;
sam ``releaseDateYear`` odrzuca (400), a ``releaseDate: "2025"`` zapisuje
jako 1970-01-01T00:33:45Z. Formularz ma jedno pole tekstowe, które przyjmuje
pełną datę albo miesiąc i rok; sam rok jest odrzucany.
"""

import datetime
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from bpp.admin.helpers.fieldsets import OPENACCESS_FIELDSET
from bpp.admin.helpers.openaccess import (
    POLE_FORMULARZA,
    formatuj_date_udostepnienia,
    parsuj_date_udostepnienia,
)
from bpp.models import Tryb_OpenAccess_Wydawnictwo_Ciagle
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_integrator.importer.helpers import importuj_openaccess

POLE_DATA = "openaccess_data_opublikowania"
POLE_ROK = "openaccess_rok_udostepnienia"
POLE_MIESIAC = "openaccess_miesiac_udostepnienia"

REKORDY = ["wydawnictwo_ciagle", "wydawnictwo_zwarte"]


# --------------------------------------------------------------------------
# Parsowanie i formatowanie wpisu
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tekst",
    ["2025-12-30", "2025.12.30", "30.12.2025", " 30.12.2025 ", "2025/12/30"],
)
def test_parsuj_pelna_data(tekst):
    assert parsuj_date_udostepnienia(tekst) == (
        datetime.date(2025, 12, 30),
        None,
        None,
    )


@pytest.mark.parametrize(
    "tekst,miesiac",
    [("2025-12", 12), ("2025.12", 12), ("12.2025", 12), ("2025-3", 3), ("3.2025", 3)],
)
def test_parsuj_miesiac_i_rok(tekst, miesiac):
    assert parsuj_date_udostepnienia(tekst) == (None, 2025, miesiac)


@pytest.mark.parametrize("tekst", ["", "   ", None])
def test_parsuj_pusty(tekst):
    assert parsuj_date_udostepnienia(tekst) == (None, None, None)


def test_parsuj_sam_rok_odrzucony_z_komunikatem_o_pbn():
    with pytest.raises(ValidationError) as exc:
        parsuj_date_udostepnienia("2025")
    assert "PBN wymaga co najmniej miesiąca i roku" in exc.value.messages[0]


@pytest.mark.parametrize(
    "tekst", ["31.02.2025", "13.2025", "2025-13", "grudzień 2025", "2025-12-30-1"]
)
def test_parsuj_bledne(tekst):
    with pytest.raises(ValidationError):
        parsuj_date_udostepnienia(tekst)


def test_formatuj():
    assert (
        formatuj_date_udostepnienia(datetime.date(2025, 12, 30), None, None)
        == "30.12.2025"
    )
    assert formatuj_date_udostepnienia(None, 2025, 3) == "03.2025"
    assert formatuj_date_udostepnienia(None, None, None) == ""


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_clean_odrzuca_date_i_miesiac_z_rokiem_naraz(wydawnictwo_ciagle):
    wydawnictwo_ciagle.openaccess_data_opublikowania = datetime.date(2025, 12, 31)
    wydawnictwo_ciagle.openaccess_rok_udostepnienia = 2025
    wydawnictwo_ciagle.openaccess_miesiac_udostepnienia = 12

    with pytest.raises(ValidationError) as exc:
        wydawnictwo_ciagle.clean()

    assert set(exc.value.message_dict) == {POLE_DATA, POLE_ROK, POLE_MIESIAC}


@pytest.mark.django_db
def test_clean_odrzuca_sam_rok(wydawnictwo_zwarte):
    wydawnictwo_zwarte.openaccess_rok_udostepnienia = 2025

    with pytest.raises(ValidationError) as exc:
        wydawnictwo_zwarte.clean()

    assert "PBN wymaga co najmniej miesiąca i roku" in str(exc.value)


@pytest.mark.django_db
def test_clean_odrzuca_sam_miesiac(wydawnictwo_zwarte):
    wydawnictwo_zwarte.openaccess_miesiac_udostepnienia = 12

    with pytest.raises(ValidationError) as exc:
        wydawnictwo_zwarte.clean()

    assert POLE_ROK in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rok,miesiac",
    [(1899, 1), (datetime.date.today().year + 11, 1), (2025, 0), (2025, 13)],
)
def test_clean_zakresy(wydawnictwo_zwarte, rok, miesiac):
    wydawnictwo_zwarte.openaccess_rok_udostepnienia = rok
    wydawnictwo_zwarte.openaccess_miesiac_udostepnienia = miesiac

    with pytest.raises(ValidationError):
        wydawnictwo_zwarte.clean()


@pytest.mark.django_db
def test_clean_miesiac_i_rok_ok(wydawnictwo_zwarte):
    wydawnictwo_zwarte.openaccess_rok_udostepnienia = 2025
    wydawnictwo_zwarte.openaccess_miesiac_udostepnienia = 12
    wydawnictwo_zwarte.clean()  # nie rzuca


# --------------------------------------------------------------------------
# Formularz w adminie
# --------------------------------------------------------------------------


def test_openaccess_fieldset_ma_jedno_pole_daty():
    pola = OPENACCESS_FIELDSET[1]["fields"]
    assert POLE_FORMULARZA in pola
    for pole in (POLE_DATA, POLE_ROK, POLE_MIESIAC):
        assert pole not in pola


def _formularz(admin_app, obj):
    nazwa = obj._meta.model_name
    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    return page, page.forms[f"{nazwa}_form"]


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", REKORDY)
def test_admin_pokazuje_pole_z_pomoca(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    page, form = _formularz(admin_app, obj)

    assert POLE_FORMULARZA in form.fields
    assert "OpenAccess: data udostępnienia (dzień lub miesiąc i rok)" in page.text
    assert "12.2025" in page.text  # przykład w pomocy


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", REKORDY)
@pytest.mark.parametrize("wpis", ["12.2025", "2025-12", "2025.12"])
def test_admin_zapisuje_miesiac_i_rok(rekord, wpis, request, admin_app):
    obj = request.getfixturevalue(rekord)
    obj.openaccess_data_opublikowania = datetime.date(2025, 12, 31)
    obj.save()
    _, form = _formularz(admin_app, obj)
    form[POLE_FORMULARZA].value = wpis
    res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert obj.openaccess_data_opublikowania is None
    assert obj.openaccess_rok_udostepnienia == 2025
    assert obj.openaccess_miesiac_udostepnienia == 12


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", REKORDY)
def test_admin_zapisuje_pelna_date_i_czysci_miesiac_rok(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    obj.openaccess_rok_udostepnienia = 2025
    obj.openaccess_miesiac_udostepnienia = 12
    obj.save()
    _, form = _formularz(admin_app, obj)
    assert form[POLE_FORMULARZA].value == "12.2025"
    form[POLE_FORMULARZA].value = "30.12.2025"
    res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert obj.openaccess_data_opublikowania == datetime.date(2025, 12, 30)
    assert obj.openaccess_rok_udostepnienia is None
    assert obj.openaccess_miesiac_udostepnienia is None


@pytest.mark.django_db
def test_admin_pokazuje_pelna_date_w_spojnym_formacie(wydawnictwo_ciagle, admin_app):
    wydawnictwo_ciagle.openaccess_data_opublikowania = datetime.date(2025, 3, 5)
    wydawnictwo_ciagle.save()
    _, form = _formularz(admin_app, wydawnictwo_ciagle)

    assert form[POLE_FORMULARZA].value == "05.03.2025"


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", REKORDY)
def test_admin_czysci_wszystkie_pola(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    obj.openaccess_data_opublikowania = datetime.date(2025, 12, 31)
    obj.save()
    _, form = _formularz(admin_app, obj)
    form[POLE_FORMULARZA].value = ""
    res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert obj.openaccess_data_opublikowania is None
    assert obj.openaccess_rok_udostepnienia is None
    assert obj.openaccess_miesiac_udostepnienia is None


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", REKORDY)
def test_admin_odrzuca_sam_rok(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    _, form = _formularz(admin_app, obj)
    form[POLE_FORMULARZA].value = "2025"
    res = form.submit()

    assert res.status_code == 200
    assert "PBN wymaga co najmniej miesiąca i roku" in res.text
    obj.refresh_from_db()
    assert obj.openaccess_rok_udostepnienia is None


@pytest.mark.django_db
def test_admin_blad_zakresu_roku_przy_polu_formularza(wydawnictwo_ciagle, admin_app):
    """Błąd z ``clean()`` modelu trafia do pola formularza, nie wywala 500."""
    _, form = _formularz(admin_app, wydawnictwo_ciagle)
    form[POLE_FORMULARZA].value = "12.1899"
    res = form.submit()

    assert res.status_code == 200
    assert "spoza dopuszczalnego zakresu" in res.text
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.openaccess_rok_udostepnienia is None


@pytest.mark.django_db
def test_admin_stary_sam_rok_wymusza_uzupelnienie(wydawnictwo_ciagle, admin_app):
    """Niekompletne dane (sam rok) są pokazane, a zapis prosi o miesiąc."""
    type(wydawnictwo_ciagle).objects.filter(pk=wydawnictwo_ciagle.pk).update(
        openaccess_rok_udostepnienia=2025
    )
    _, form = _formularz(admin_app, wydawnictwo_ciagle)
    assert form[POLE_FORMULARZA].value == "2025"
    res = form.submit()

    assert res.status_code == 200
    assert "PBN wymaga co najmniej miesiąca i roku" in res.text


# --------------------------------------------------------------------------
# Eksport do PBN
# --------------------------------------------------------------------------


def _release_date(**pola):
    domyslne = {
        POLE_DATA: None,
        POLE_ROK: None,
        POLE_MIESIAC: None,
        "public_dostep_dnia": None,
        "dostep_dnia": None,
    }
    domyslne.update(pola)
    adapter = WydawnictwoPBNAdapter.__new__(WydawnictwoPBNAdapter)
    adapter.original = SimpleNamespace(**domyslne)
    oa = {}
    adapter._build_open_access_release_date(oa)
    return oa


def test_eksport_miesiac_i_rok():
    oa = _release_date(**{POLE_ROK: 2025, POLE_MIESIAC: 12})

    assert oa == {"releaseDateMonth": "DECEMBER", "releaseDateYear": 2025}


def test_eksport_styczen_to_january():
    oa = _release_date(**{POLE_ROK: 2025, POLE_MIESIAC: 1})

    assert oa["releaseDateMonth"] == "JANUARY"


def test_eksport_nigdy_nie_wysyla_samego_roku():
    """Strażnik: PBN odrzuca sam rok, a ``releaseDate: "2025"`` psuje datę."""
    oa = _release_date(**{POLE_ROK: 2025})

    assert "releaseDateYear" not in oa
    assert oa.get("releaseDate") != "2025"
    assert oa == {}


def test_eksport_pelna_data_bez_zmian():
    oa = _release_date(**{POLE_DATA: datetime.date(2025, 12, 31)})

    assert oa == {"releaseDate": "2025-12-31"}


def test_eksport_miesiac_i_rok_wygrywaja_z_datami_www():
    oa = _release_date(
        **{
            POLE_ROK: 2025,
            POLE_MIESIAC: 6,
            "public_dostep_dnia": datetime.date(2024, 1, 1),
            "dostep_dnia": datetime.date(2023, 1, 1),
        }
    )

    assert oa == {"releaseDateMonth": "JUNE", "releaseDateYear": 2025}


def test_eksport_bez_dat_oa_fallback_na_date_www_bez_zmian():
    oa = _release_date(public_dostep_dnia=datetime.date(2024, 5, 6))

    assert oa == {"releaseDate": "2024-05-06"}


def test_eksport_bez_zadnej_daty_nic_nie_wysyla():
    assert _release_date() == {}


# --------------------------------------------------------------------------
# Import z PBN
# --------------------------------------------------------------------------


def _importuj(rekord, oa_json):
    pbn_json = {"openAccess": dict(oa_json)}
    importuj_openaccess(
        rekord,
        pbn_json,
        klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
    )
    return pbn_json


@pytest.mark.django_db
@pytest.mark.parametrize("rok", [2025, "2025"])
def test_import_miesiac_i_rok_bez_zmyslania_dnia(wydawnictwo_ciagle, rok):
    pbn_json = _importuj(
        wydawnictwo_ciagle, {"releaseDateYear": rok, "releaseDateMonth": "DECEMBER"}
    )

    assert wydawnictwo_ciagle.openaccess_data_opublikowania is None
    assert wydawnictwo_ciagle.openaccess_rok_udostepnienia == 2025
    assert wydawnictwo_ciagle.openaccess_miesiac_udostepnienia == 12
    assert pbn_json == {}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "oa_json",
    [
        {"releaseDateYear": 2020},
        {"releaseDateYear": "2020", "releaseDateMonth": None},
    ],
)
def test_import_sam_rok_pomijany_bez_zmyslania(wydawnictwo_ciagle, oa_json):
    pbn_json = _importuj(wydawnictwo_ciagle, oa_json)

    assert wydawnictwo_ciagle.openaccess_data_opublikowania is None
    assert wydawnictwo_ciagle.openaccess_rok_udostepnienia is None
    assert wydawnictwo_ciagle.openaccess_miesiac_udostepnienia is None
    assert pbn_json == {}


@pytest.mark.django_db
def test_import_nieznany_miesiac_zglasza_blad(wydawnictwo_ciagle):
    with pytest.raises(ValueError):
        _importuj(
            wydawnictwo_ciagle,
            {"releaseDateYear": 2020, "releaseDateMonth": "SMARCH"},
        )


@pytest.mark.django_db
def test_import_pelna_data_bez_zmian(wydawnictwo_ciagle):
    _importuj(
        wydawnictwo_ciagle,
        {
            "releaseDate": "2025-12-30T00:00:00",
            "releaseDateYear": 2025,
            "releaseDateMonth": "DECEMBER",
        },
    )

    assert wydawnictwo_ciagle.openaccess_data_opublikowania == datetime.date(
        2025, 12, 30
    )
    assert wydawnictwo_ciagle.openaccess_rok_udostepnienia is None
