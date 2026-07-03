"""Testy filtra i kolumny „Instytucja PBN" w adminach PBN API (multi-hosted).

W instalacji z >1 uczelnią superuser widzi w adminie wiersze ze wszystkich
uczelni. Filtr ``InstytucjaPBNFilter`` (i wariant V2) pozwala zawęzić listę do
jednej instytucji PBN, a warunkowa kolumna ``instytucja_pbn`` pokazuje, z której
instytucji jest wiersz. Na instalacji jednouczelnianej filtr i kolumna znikają.

Niezmiennik, na którym stoi filtr:

    row.institutionId_id == uczelnia.pbn_uid_id
"""

import pytest
from django.contrib import admin
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.admin.oswiadczenieinstytucji import OswiadczeniaInstytucjiAdmin
from pbn_api.admin.publikacjainstytucji_v1 import (
    PublikacjaInstytucjiAdmin as PublikacjaInstytucjiV1Admin,
)
from pbn_api.admin.publikacjainstytucji_v2 import (
    PublikacjaInstytucjiAdmin as PublikacjaInstytucjiV2Admin,
)
from pbn_api.models import (
    Institution,
    OswiadczenieInstytucji,
    PublikacjaInstytucji,
    PublikacjaInstytucji_V2,
)


@pytest.fixture
def institution1(db):
    return baker.make(Institution, name="Instytucja U1")


@pytest.fixture
def institution2(db):
    return baker.make(Institution, name="Instytucja U2")


@pytest.fixture
def uczelnia1(db, institution1):
    return baker.make(Uczelnia, skrot="U1", nazwa="Uczelnia 1", pbn_uid=institution1)


@pytest.fixture
def uczelnia2(db, institution2):
    return baker.make(Uczelnia, skrot="U2", nazwa="Uczelnia 2", pbn_uid=institution2)


def _changelist_queryset_pks(admin_client, model, **params):
    """Odpal changelist admina jako superuser i zwróć pk-i po filtrach."""
    opts = model._meta
    url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
    res = admin_client.get(url, params)
    assert res.status_code == 200, res.status_code
    cl = res.context_data["cl"]
    return set(cl.queryset.values_list("pk", flat=True))


# ---------------------------------------------------------------------------
# lookups(): bramka „tylko gdy >1 uczelnia"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_filter_hidden_with_single_uczelnia(rf, uczelnia1):
    """Jedna uczelnia → lookups() zwraca [] → Django nie renderuje filtra."""
    from pbn_api.admin.filters import InstytucjaPBNFilter

    flt = object.__new__(InstytucjaPBNFilter)
    assert flt.lookups(rf.get("/"), None) == []


@pytest.mark.django_db
def test_filter_shown_with_multiple_uczelnie(rf, uczelnia1, uczelnia2):
    """Dwie uczelnie → lookups() zwraca po jednym wpisie (pbn_uid_id, nazwa)."""
    from pbn_api.admin.filters import InstytucjaPBNFilter

    flt = object.__new__(InstytucjaPBNFilter)
    choices = flt.lookups(rf.get("/"), None)

    assert {value for value, label in choices} == {
        uczelnia1.pbn_uid_id,
        uczelnia2.pbn_uid_id,
    }
    assert {label for value, label in choices} == {"Uczelnia 1", "Uczelnia 2"}


@pytest.mark.django_db
def test_filter_skips_uczelnia_without_pbn_uid(rf, uczelnia1, uczelnia2):
    """Uczelnia bez pbn_uid nie trafia do wyboru filtra."""
    from pbn_api.admin.filters import InstytucjaPBNFilter

    baker.make(Uczelnia, skrot="U3", nazwa="Bez PBN", pbn_uid=None)

    flt = object.__new__(InstytucjaPBNFilter)
    values = {value for value, label in flt.lookups(rf.get("/"), None)}
    assert values == {uczelnia1.pbn_uid_id, uczelnia2.pbn_uid_id}


# ---------------------------------------------------------------------------
# get_list_display(): warunkowa kolumna
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "admin_cls,model",
    [
        (PublikacjaInstytucjiV1Admin, PublikacjaInstytucji),
        (PublikacjaInstytucjiV2Admin, PublikacjaInstytucji_V2),
        (OswiadczeniaInstytucjiAdmin, OswiadczenieInstytucji),
    ],
)
def test_column_absent_with_single_uczelnia(rf, uczelnia1, admin_cls, model):
    admin_obj = admin_cls(model, admin.site)
    assert "instytucja_pbn" not in admin_obj.get_list_display(rf.get("/"))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "admin_cls,model",
    [
        (PublikacjaInstytucjiV1Admin, PublikacjaInstytucji),
        (PublikacjaInstytucjiV2Admin, PublikacjaInstytucji_V2),
        (OswiadczeniaInstytucjiAdmin, OswiadczenieInstytucji),
    ],
)
def test_column_present_with_multiple_uczelnie(
    rf, uczelnia1, uczelnia2, admin_cls, model
):
    admin_obj = admin_cls(model, admin.site)
    assert "instytucja_pbn" in admin_obj.get_list_display(rf.get("/"))


# ---------------------------------------------------------------------------
# instytucja_pbn(): co pokazuje kolumna
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_column_value_v1_shows_institution(institution1):
    admin_obj = PublikacjaInstytucjiV1Admin(PublikacjaInstytucji, admin.site)
    pi = baker.make(PublikacjaInstytucji, institutionId=institution1)
    assert admin_obj.instytucja_pbn(pi) == institution1


@pytest.mark.django_db
def test_column_value_oswiadczenia_shows_institution(institution1):
    admin_obj = OswiadczeniaInstytucjiAdmin(OswiadczenieInstytucji, admin.site)
    osw = baker.make(OswiadczenieInstytucji, institutionId=institution1)
    assert admin_obj.instytucja_pbn(osw) == institution1


@pytest.mark.django_db
def test_column_value_v2_shows_uczelnia(uczelnia1):
    admin_obj = PublikacjaInstytucjiV2Admin(PublikacjaInstytucji_V2, admin.site)
    piv2 = baker.make(PublikacjaInstytucji_V2, uczelnia=uczelnia1)
    assert admin_obj.instytucja_pbn(piv2) == uczelnia1


# ---------------------------------------------------------------------------
# Changelist end-to-end: filtr faktycznie zawęża zbiór wierszy
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_v1_changelist_filters_by_institution(
    admin_client, uczelnia1, uczelnia2, institution1, institution2
):
    pi1 = baker.make(PublikacjaInstytucji, institutionId=institution1)
    baker.make(PublikacjaInstytucji, institutionId=institution2)

    pks = _changelist_queryset_pks(
        admin_client, PublikacjaInstytucji, instytucja_pbn=institution1.pk
    )
    assert pks == {pi1.pk}


@pytest.mark.django_db
def test_oswiadczenia_changelist_filters_by_institution(
    admin_client, uczelnia1, uczelnia2, institution1, institution2
):
    osw1 = baker.make(OswiadczenieInstytucji, institutionId=institution1)
    baker.make(OswiadczenieInstytucji, institutionId=institution2)

    pks = _changelist_queryset_pks(
        admin_client, OswiadczenieInstytucji, instytucja_pbn=institution1.pk
    )
    assert pks == {osw1.pk}


@pytest.mark.django_db
def test_v2_changelist_filters_by_uczelnia(
    admin_client, uczelnia1, uczelnia2, institution1
):
    piv2_1 = baker.make(PublikacjaInstytucji_V2, uczelnia=uczelnia1)
    baker.make(PublikacjaInstytucji_V2, uczelnia=uczelnia2)

    # Wartość filtra to pbn_uid_id (== institutionId), a V2 mapuje przez uczelnia.
    pks = _changelist_queryset_pks(
        admin_client, PublikacjaInstytucji_V2, instytucja_pbn=institution1.pk
    )
    assert pks == {piv2_1.uuid}
