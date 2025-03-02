import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_api.models import Publication

from bpp.models import Autor_Dyscyplina, Wydawnictwo_Zwarte
from bpp.tests import normalize_html, select_select2_autocomplete
from bpp.tests.test_selenium.test_raporty import submit_admin_page

from django_bpp.selenium_util import wait_for, wait_for_page_load

TEST_PBN_ID = 50000


@pytest.mark.parametrize(
    "fld,value",
    [
        # ("pbn_uid", TEST_PBN_ID),
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


def test_Wydawnictwo_Zwarte_Autor_Admin_forwarding_works(
    admin_browser,
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    dyscyplina1,
    jednostka,
    live_server,
):
    rok = 2022

    Autor_Dyscyplina.objects.all().delete()

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_zwarte.rok = rok
    wydawnictwo_zwarte.save()

    aj = wydawnictwo_zwarte.dodaj_autora(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
    )

    url = (
        f"/admin/bpp/wydawnictwo_zwarte_autor/{aj.pk}/change/"
        f"?_changelist_filters=rekord__id__exact%3D{wydawnictwo_zwarte.pk}"
    )

    admin_browser.visit(live_server.url + url)
    wait_for(lambda: admin_browser.find_by_name("rok"))

    select_select2_autocomplete(
        admin_browser, "id_dyscyplina_naukowa", dyscyplina1.nazwa
    )

    with wait_for_page_load(admin_browser):
        submit_admin_page(admin_browser)

    wait_for(lambda: admin_browser.html.find("pomyślnie") >= 0)

    aj.refresh_from_db()

    assert aj.dyscyplina_naukowa.pk == dyscyplina1.pk
