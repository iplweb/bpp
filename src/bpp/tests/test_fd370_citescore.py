"""FD#370: CiteScore i jego najwyższy percentyl przy rocznej punktacji źródła.

Dwa nowe pola ``Punktacja_Zrodla`` oraz podpowiedź kwartyla Scopus liczona
z percentyla — wyłącznie wtedy, gdy kwartyl jest pusty.
"""

import importlib
from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from model_bakery import baker

from bpp.admin.zrodlo import Punktacja_ZrodlaInline
from bpp.models import Punktacja_Zrodla, Zrodlo
from bpp.models.abstract import POLA_PUNKTACJI
from bpp.models.zrodlo import kwartyl_scopus_z_percentyla


@pytest.mark.parametrize(
    "percentyl,kwartyl",
    [
        (100, 1),
        (99, 1),
        (75, 1),
        (74, 2),
        (50, 2),
        (49, 3),
        (25, 3),
        (24, 4),
        (0, 4),
        (None, None),
        (101, None),
        (-1, None),
    ],
)
def test_kwartyl_scopus_z_percentyla(percentyl, kwartyl):
    assert kwartyl_scopus_z_percentyla(percentyl) == kwartyl


@pytest.fixture
def zrodlo_fd370(db):
    return baker.make(Zrodlo, nazwa="Czasopismo FD370")


def _pz(zrodlo, **kw):
    return Punktacja_Zrodla(zrodlo=zrodlo, rok=2025, **kw)


@pytest.mark.django_db
def test_pola_sa_opcjonalne(zrodlo_fd370):
    pz = _pz(zrodlo_fd370)
    pz.full_clean()
    pz.save()
    pz.refresh_from_db()
    assert pz.citescore is None
    assert pz.citescore_percentyl is None
    assert pz.kwartyl_w_scopus is None


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", [Decimal("0.0"), Decimal("7.3"), Decimal("649.8")])
def test_citescore_poprawne_wartosci(zrodlo_fd370, wartosc):
    pz = _pz(zrodlo_fd370, citescore=wartosc)
    pz.full_clean()
    pz.save()
    pz.refresh_from_db()
    assert pz.citescore == wartosc


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", [Decimal("-0.1"), Decimal("7.35")])
def test_citescore_bledne_wartosci(zrodlo_fd370, wartosc):
    with pytest.raises(ValidationError) as exc:
        _pz(zrodlo_fd370, citescore=wartosc).full_clean()
    assert "citescore" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", [0, 50, 100])
def test_percentyl_poprawne_wartosci(zrodlo_fd370, wartosc):
    _pz(zrodlo_fd370, citescore_percentyl=wartosc).full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", [-1, 101])
def test_percentyl_bledne_wartosci(zrodlo_fd370, wartosc):
    with pytest.raises(ValidationError) as exc:
        _pz(zrodlo_fd370, citescore_percentyl=wartosc).full_clean()
    assert "citescore_percentyl" in exc.value.message_dict


@pytest.mark.django_db
def test_zapis_uzupelnia_pusty_kwartyl_scopus(zrodlo_fd370):
    pz = _pz(zrodlo_fd370, citescore_percentyl=80)
    pz.save()
    pz.refresh_from_db()
    assert pz.kwartyl_w_scopus == 1
    # Kwartyl WoS nie ma nic wspólnego z CiteScore.
    assert pz.kwartyl_w_wos is None


@pytest.mark.django_db
def test_zapis_nie_nadpisuje_recznego_kwartyla(zrodlo_fd370):
    pz = _pz(zrodlo_fd370, citescore_percentyl=80, kwartyl_w_scopus=3)
    pz.save()
    pz.refresh_from_db()
    assert pz.kwartyl_w_scopus == 3

    # Późniejsza zmiana percentyla też nie rusza istniejącego kwartyla.
    pz.citescore_percentyl = 10
    pz.save()
    pz.refresh_from_db()
    assert pz.kwartyl_w_scopus == 3


@pytest.mark.django_db
def test_zapis_bez_percentyla_zostawia_pusty_kwartyl(zrodlo_fd370):
    pz = _pz(zrodlo_fd370, citescore=Decimal("3.1"))
    pz.save()
    pz.refresh_from_db()
    assert pz.kwartyl_w_scopus is None


@pytest.mark.django_db
def test_zapis_z_update_fields_utrwala_podpowiedziany_kwartyl(zrodlo_fd370):
    pz = _pz(zrodlo_fd370)
    pz.save()

    pz.citescore_percentyl = 30
    pz.save(update_fields=["citescore_percentyl"])

    pz = Punktacja_Zrodla.objects.get(pk=pz.pk)
    assert pz.citescore_percentyl == 30
    assert pz.kwartyl_w_scopus == 3


def test_citescore_nie_jest_kopiowany_do_publikacji():
    # POLA_PUNKTACJI to pola przepisywane między źródłem a pracą; publikacje
    # nie mają CiteScore, więc dopisanie go tam wywaliłoby „Uzupełnij punktację”.
    assert "citescore" not in POLA_PUNKTACJI
    assert "citescore_percentyl" not in POLA_PUNKTACJI


def _formset_inline(rf, admin_user):
    request = rf.get("/")
    request.user = admin_user
    inline = Punktacja_ZrodlaInline(Zrodlo, admin.site)
    return inline.get_formset(request)


@pytest.mark.django_db
def test_admin_tabela_punktacji_ma_nowe_kolumny(rf, admin_user):
    fields = list(_formset_inline(rf, admin_user).form.base_fields)
    assert fields.index("citescore") < fields.index("kwartyl_w_scopus")
    assert fields.index("citescore_percentyl") < fields.index("kwartyl_w_scopus")
    # Dotychczasowe kolumny zostają.
    for pole in ("rok", "impact_factor", "punktacja_snip", "kwartyl_w_wos"):
        assert pole in fields


def _dane_formsetu(**wiersz):
    dane = {
        "punktacja_zrodla_set-TOTAL_FORMS": "1",
        "punktacja_zrodla_set-INITIAL_FORMS": "0",
        "punktacja_zrodla_set-MIN_NUM_FORMS": "0",
        "punktacja_zrodla_set-MAX_NUM_FORMS": "1000",
        "punktacja_zrodla_set-0-rok": "2025",
        "punktacja_zrodla_set-0-punkty_kbn": "0",
        "punktacja_zrodla_set-0-impact_factor": "0",
        "punktacja_zrodla_set-0-index_copernicus": "0",
        "punktacja_zrodla_set-0-punktacja_snip": "0",
        "punktacja_zrodla_set-0-punktacja_wewnetrzna": "0",
        "punktacja_zrodla_set-0-kwartyl_w_scopus": "",
        "punktacja_zrodla_set-0-kwartyl_w_wos": "",
    }
    for pole, wartosc in wiersz.items():
        dane[f"punktacja_zrodla_set-0-{pole}"] = wartosc
    return dane


@pytest.mark.django_db
def test_admin_zapis_z_przecinkiem_i_podpowiedzia_kwartyla(
    rf, admin_user, zrodlo_fd370
):
    FormSet = _formset_inline(rf, admin_user)
    formset = FormSet(
        _dane_formsetu(citescore="12,5", citescore_percentyl="62"),
        instance=zrodlo_fd370,
    )
    assert formset.is_valid(), formset.errors
    formset.save()

    pz = zrodlo_fd370.punktacja_zrodla_set.get(rok=2025)
    assert pz.citescore == Decimal("12.5")
    assert pz.citescore_percentyl == 62
    assert pz.kwartyl_w_scopus == 2


@pytest.mark.django_db
def test_admin_reczny_kwartyl_ma_pierwszenstwo(rf, admin_user, zrodlo_fd370):
    FormSet = _formset_inline(rf, admin_user)
    formset = FormSet(
        _dane_formsetu(citescore_percentyl="62", kwartyl_w_scopus="4"),
        instance=zrodlo_fd370,
    )
    assert formset.is_valid(), formset.errors
    formset.save()

    assert zrodlo_fd370.punktacja_zrodla_set.get(rok=2025).kwartyl_w_scopus == 4


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pole,wartosc",
    [
        ("citescore", "-1"),
        ("citescore", "1,25"),
        ("citescore_percentyl", "101"),
        ("citescore_percentyl", "-5"),
    ],
)
def test_admin_odrzuca_wartosci_spoza_zakresu(
    rf, admin_user, zrodlo_fd370, pole, wartosc
):
    FormSet = _formset_inline(rf, admin_user)
    formset = FormSet(_dane_formsetu(**{pole: wartosc}), instance=zrodlo_fd370)
    assert not formset.is_valid()
    assert pole in formset.errors[0]


def test_migracja_dodaje_tylko_dwa_opcjonalne_pola():
    mod = importlib.import_module("bpp.migrations.0532_punktacja_zrodla_citescore")
    operacje = mod.Migration.operations
    assert [(o.model_name, o.name) for o in operacje] == [
        ("punktacja_zrodla", "citescore"),
        ("punktacja_zrodla", "citescore_percentyl"),
    ]
    # Istniejące wiersze punktacji zostają bez wartości — żadnego przeliczania.
    assert all(o.field.null and o.field.blank for o in operacje)
