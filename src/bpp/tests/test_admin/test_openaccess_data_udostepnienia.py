"""Freshdesk #281: the open access release date must be editable in admin.

``openaccess_data_opublikowania`` is sent to PBN as the OpenAccess release
date, but it was missing from ``OPENACCESS_FIELDSET``, so editors could not
enter it -- only the PBN importer filled it in.
"""

import datetime

import pytest
from django.urls import reverse

from bpp.admin.helpers.fieldsets import OPENACCESS_FIELDSET
from bpp.admin.helpers.openaccess import POLE_FORMULARZA

POLE = "openaccess_data_opublikowania"


def test_openaccess_fieldset_zawiera_date_udostepnienia():
    # FD#281 (cd.): data jest edytowana przez jedno pole tekstowe
    # „dzień lub miesiąc i rok”, rozkładane na pola modelu.
    assert POLE_FORMULARZA in OPENACCESS_FIELDSET[1]["fields"]


@pytest.mark.parametrize("rekord", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_admin_change_pokazuje_date_udostepnienia_oa(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    nazwa = obj._meta.model_name

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))

    assert POLE_FORMULARZA in page.forms[f"{nazwa}_form"].fields
    assert "OpenAccess: data udostępnienia" in page.text
    assert "wysyłana do PBN" in page.text


@pytest.mark.parametrize("rekord", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_admin_zapisuje_date_udostepnienia_oa(rekord, request, admin_app):
    obj = request.getfixturevalue(rekord)
    nazwa = obj._meta.model_name
    assert getattr(obj, POLE) is None

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    form = page.forms[f"{nazwa}_form"]
    form[POLE_FORMULARZA].value = "2024-03-15"
    res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert getattr(obj, POLE) == datetime.date(2024, 3, 15)
