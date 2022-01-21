import pytest
from django.urls import reverse
from model_mommy import mommy

from bpp.models import Wydawnictwo_Ciagle
from bpp.tests import normalize_html


@pytest.mark.parametrize(
    "fld,value",
    [
        ("doi", "10.10/123123"),
        ("www", "https://foobar.pl"),
        ("public_www", "https://foobar.pl"),
    ],
)
def test_Wydawnictwo_Ciagle_Admin_sprawdz_duplikaty_www_doi(
    admin_app, zrodlo, fld, value
):
    mommy.make(Wydawnictwo_Ciagle, **{fld: value})
    w2 = mommy.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)

    url = "admin:bpp_wydawnictwo_ciagle_change"
    page = admin_app.get(reverse(url, args=(w2.pk,)))

    page.forms["wydawnictwo_ciagle_form"][fld].value = value
    res = page.forms["wydawnictwo_ciagle_form"].submit().maybe_follow()

    assert "Istnieją rekordy z identycznym polem" in normalize_html(
        res.content.decode("utf-8")
    )
