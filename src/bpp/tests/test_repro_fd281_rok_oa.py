"""Freshdesk #281: sam rok udostępnienia w otwartym dostępie.

Klient nie chce wpisywać pełnej daty udostępnienia OA (dzień i miesiąc są
zmyślone) — chce wysłać do PBN sam rok (``releaseDateYear``). Redakcja
wpisuje ALBO pełną datę, ALBO sam rok; eksport wysyła rok bez miesiąca,
a import z PBN zapisuje sam rok zamiast zmyślać 1 stycznia.
"""

import datetime
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from bpp.admin.helpers.fieldsets import OPENACCESS_FIELDSET
from bpp.models import Tryb_OpenAccess_Wydawnictwo_Ciagle
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_integrator.importer.helpers import importuj_openaccess

POLE_ROK = "openaccess_rok_udostepnienia"
POLE_DATA = "openaccess_data_opublikowania"


# --------------------------------------------------------------------------
# Model i formularz w adminie
# --------------------------------------------------------------------------


def test_openaccess_fieldset_zawiera_rok_tuz_po_dacie():
    pola = OPENACCESS_FIELDSET[1]["fields"]
    assert POLE_ROK in pola
    assert pola.index(POLE_ROK) == pola.index(POLE_DATA) + 1


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_admin_zapisuje_sam_rok_udostepnienia(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    nazwa = obj._meta.model_name

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    assert "OpenAccess: rok udostępnienia" in page.text
    form = page.forms[f"{nazwa}_form"]
    form[POLE_ROK].value = "2025"
    res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert getattr(obj, POLE_ROK) == 2025
    assert getattr(obj, POLE_DATA) is None


@pytest.mark.django_db
@pytest.mark.parametrize("rekord", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_admin_nie_pozwala_na_date_i_rok_naraz(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    nazwa = obj._meta.model_name

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    form = page.forms[f"{nazwa}_form"]
    form[POLE_DATA].value = "2025-12-31"
    form[POLE_ROK].value = "2025"
    res = form.submit()

    assert res.status_code == 200
    assert "nie oba naraz" in res.text
    obj.refresh_from_db()
    assert getattr(obj, POLE_ROK) is None
    assert getattr(obj, POLE_DATA) is None


@pytest.mark.django_db
def test_clean_odrzuca_date_i_rok_naraz(wydawnictwo_ciagle):
    wydawnictwo_ciagle.openaccess_data_opublikowania = datetime.date(2025, 12, 31)
    wydawnictwo_ciagle.openaccess_rok_udostepnienia = 2025

    with pytest.raises(ValidationError) as exc:
        wydawnictwo_ciagle.clean()

    assert set(exc.value.message_dict) == {POLE_DATA, POLE_ROK}


@pytest.mark.django_db
@pytest.mark.parametrize("rok", [1899, datetime.date.today().year + 11])
def test_rok_spoza_zakresu_jest_odrzucany(wydawnictwo_zwarte, rok):
    wydawnictwo_zwarte.openaccess_rok_udostepnienia = rok

    with pytest.raises(ValidationError) as exc:
        wydawnictwo_zwarte.clean()

    assert POLE_ROK in exc.value.message_dict


@pytest.mark.django_db
def test_admin_odrzuca_rok_spoza_zakresu(wydawnictwo_ciagle, admin_app):
    page = admin_app.get(
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))
    )
    form = page.forms["wydawnictwo_ciagle_form"]
    form[POLE_ROK].value = "1899"
    res = form.submit()

    assert res.status_code == 200
    wydawnictwo_ciagle.refresh_from_db()
    assert getattr(wydawnictwo_ciagle, POLE_ROK) is None


@pytest.mark.django_db
def test_sam_rok_przechodzi_walidacje(wydawnictwo_zwarte):
    wydawnictwo_zwarte.openaccess_rok_udostepnienia = datetime.date.today().year
    wydawnictwo_zwarte.clean()  # nie rzuca


# --------------------------------------------------------------------------
# Eksport do PBN
# --------------------------------------------------------------------------


def _release_date(**pola):
    domyslne = {
        POLE_DATA: None,
        POLE_ROK: None,
        "public_dostep_dnia": None,
        "dostep_dnia": None,
    }
    domyslne.update(pola)
    adapter = WydawnictwoPBNAdapter.__new__(WydawnictwoPBNAdapter)
    adapter.original = SimpleNamespace(**domyslne)
    oa = {}
    adapter._build_open_access_release_date(oa)
    return oa


def test_eksport_sam_rok_bez_miesiaca():
    oa = _release_date(**{POLE_ROK: 2025})

    assert oa == {"releaseDateYear": 2025}


def test_eksport_pelna_data_bez_zmian():
    oa = _release_date(**{POLE_DATA: datetime.date(2025, 12, 31)})

    assert oa == {"releaseDate": "2025-12-31"}


def test_eksport_rok_oa_wygrywa_z_datami_www():
    oa = _release_date(
        **{
            POLE_ROK: 2025,
            "public_dostep_dnia": datetime.date(2024, 1, 1),
            "dostep_dnia": datetime.date(2023, 1, 1),
        }
    )

    assert oa == {"releaseDateYear": 2025}


def test_eksport_bez_roku_fallback_na_date_www_bez_zmian():
    oa = _release_date(public_dostep_dnia=datetime.date(2024, 5, 6))

    assert oa == {"releaseDate": "2024-05-06"}


def test_eksport_bez_zadnej_daty_nic_nie_wysyla():
    assert _release_date() == {}


# --------------------------------------------------------------------------
# Import z PBN
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "oa_json",
    [
        {"releaseDateYear": 2020},
        {"releaseDateYear": "2020"},
        {"releaseDateYear": 2020, "releaseDateMonth": None},
    ],
)
def test_import_sam_rok_trafia_do_pola_roku(wydawnictwo_ciagle, oa_json):
    pbn_json = {"openAccess": dict(oa_json)}

    importuj_openaccess(
        wydawnictwo_ciagle,
        pbn_json,
        klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
    )

    assert wydawnictwo_ciagle.openaccess_rok_udostepnienia == 2020
    assert wydawnictwo_ciagle.openaccess_data_opublikowania is None
    assert pbn_json == {}


@pytest.mark.django_db
def test_import_rok_i_miesiac_nadal_jako_data(wydawnictwo_ciagle):
    pbn_json = {
        "openAccess": {"releaseDateYear": "2020", "releaseDateMonth": "MARCH"}
    }

    importuj_openaccess(
        wydawnictwo_ciagle,
        pbn_json,
        klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
    )

    assert wydawnictwo_ciagle.openaccess_data_opublikowania == datetime.date(
        2020, 3, 1
    )
    assert wydawnictwo_ciagle.openaccess_rok_udostepnienia is None
