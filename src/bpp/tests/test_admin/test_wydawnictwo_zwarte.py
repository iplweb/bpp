import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_api.models import Publication

from bpp.models import Wydawnictwo_Zwarte
from bpp.tests import normalize_html

TEST_PBN_ID = 50000


@pytest.mark.parametrize(
    "fld,value",
    [
        ("pbn_uid", TEST_PBN_ID),
        ("doi", "10.10/123123"),
        ("www", "https://foobar.pl"),
        ("public_www", "https://foobar.pl"),
    ],
)
def test_Wydawnictwo_Zwarte_Admin_sprawdz_duplikaty_www_doi(admin_app, fld, value):
    if fld == "pbn_uid":
        value = baker.make(Publication, pk=TEST_PBN_ID)

    baker.make(Wydawnictwo_Zwarte, rok=2020, **{fld: value})
    w2 = baker.make(Wydawnictwo_Zwarte, rok=2020)
    if fld == "pbn_uid":
        value = TEST_PBN_ID  # baker.make(Publication, pk=TEST_PBN_ID)

    url = "admin:bpp_wydawnictwo_zwarte_change"
    page = admin_app.get(reverse(url, args=(w2.pk,)))

    if fld == "pbn_uid":
        page.forms["wydawnictwo_zwarte_form"][fld].force_value(value)
    else:
        page.forms["wydawnictwo_zwarte_form"][fld].value = value
    res = page.forms["wydawnictwo_zwarte_form"].submit().maybe_follow()

    assert "inne rekordy z identycznym polem" in normalize_html(
        res.content.decode("utf-8")
    )
