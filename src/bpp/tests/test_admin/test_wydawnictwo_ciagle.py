import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_api.models import Publication, SentData

from bpp import const
from bpp.models import Autor_Dyscyplina, Uczelnia, Wydawnictwo_Ciagle
from bpp.tests import normalize_html, select_select2_autocomplete
from bpp.tests.test_selenium.test_raporty import submit_admin_page

from django_bpp.selenium_util import wait_for, wait_for_page_load


def test_admin_czy_jest_przycisk_export_wydawnictwo_ciagle(
    admin_app, wydawnictwo_ciagle
):
    url = "admin:bpp_wydawnictwo_ciagle_changelist"
    page = admin_app.get(reverse(url))

    assert b"Eksport" in page.content


def test_admin_czy_jest_przycisk_crossref_wydawnictwo_ciagle(
    admin_app, wydawnictwo_ciagle
):
    url = "admin:bpp_wydawnictwo_ciagle_changelist"
    page = admin_app.get(reverse(url))

    assert b"Dodaj z CrossRef API" in page.content


def test_admin_czy_jest_przycisk_export_wydawnictwo_zwarte(
    admin_app, wydawnictwo_zwarte
):
    url = "admin:bpp_wydawnictwo_zwarte_changelist"
    page = admin_app.get(reverse(url))

    assert b"Eksport" in page.content


def test_admin_czy_jest_przycisk_export_autor(admin_app, autor):
    url = "admin:bpp_autor_changelist"
    page = admin_app.get(reverse(url))

    assert b"Eksport" in page.content


def test_wydawnictwo_ciagle_admin_zapisz_bez_linkow(
    admin_app, uczelnia, wydawnictwo_ciagle, charaktery_formalne
):
    url = "admin:bpp_wydawnictwo_ciagle_change"
    page = admin_app.get(reverse(url, args=(wydawnictwo_ciagle.pk,)))

    page.forms["wydawnictwo_ciagle_form"][
        "tytul_oryginalny"
    ].value = "Test www.onet.pl formularza"
    page.forms["wydawnictwo_ciagle_form"].submit().maybe_follow()

    wydawnictwo_ciagle.refresh_from_db()
    assert "a href" not in wydawnictwo_ciagle.tytul_oryginalny


def test_wydawnictwo_ciagle_admin_zapisz_i_wyslij_do_pbn_add_tak(
    admin_app, uczelnia, mocker
):
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.pbn_integracja = True
    uczelnia.pbn_client = mocker.Mock()
    uczelnia.save()

    url = "admin:bpp_wydawnictwo_ciagle_add"
    page = admin_app.get(reverse(url))
    assert "Zapisz i wyślij do PBN" in normalize_html(page.content.decode("utf-8"))


def test_wydawnictwo_ciagle_admin_zapisz_i_wyslij_do_pbn_add_nie(
    admin_app, uczelnia, mocker
):
    uczelnia.pbn_aktualizuj_na_biezaco = False
    uczelnia.pbn_integracja = True
    uczelnia.pbn_client = mocker.Mock()
    uczelnia.save()

    url = "admin:bpp_wydawnictwo_ciagle_add"
    page = admin_app.get(reverse(url))
    assert "Zapisz i wyślij do PBN" not in normalize_html(page.content.decode("utf-8"))


def test_wydawnictwo_ciagle_admin_zapisz_i_wyslij_do_pbn_change_tak(
    admin_app, uczelnia, mocker, wydawnictwo_ciagle, charaktery_formalne
):
    orig_pbn_client = Uczelnia.pbn_client

    try:
        pbn_client = mocker.Mock()
        Uczelnia.pbn_client = pbn_client

        uczelnia.pbn_aktualizuj_na_biezaco = True
        uczelnia.pbn_integracja = True
        uczelnia.save()

        cf = wydawnictwo_ciagle.charakter_formalny
        cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
        cf.save()

        pub = baker.make(Publication)
        SentData.objects.create(object=wydawnictwo_ciagle, data_sent={}, pbn_uid=pub)

        url = "admin:bpp_wydawnictwo_ciagle_change"
        page = admin_app.get(reverse(url, args=(wydawnictwo_ciagle.pk,)))
        assert "Zapisz i wyślij do PBN" in normalize_html(page.content.decode("utf-8"))

        page = (
            page.forms["wydawnictwo_ciagle_form"]
            .submit("_continue_and_pbn")
            .maybe_follow()
        )
        content = normalize_html(page.content.decode("utf-8"))
        assert "pomyślnie zmieniony" in content
        assert len(pbn_client.mock_calls) == 4
    finally:
        Uczelnia.pbn_client = orig_pbn_client


def test_wydawnictwo_ciagle_admin_zapisz_i_wyslij_do_pbn_change_nie(
    admin_app, uczelnia, mocker, wydawnictwo_ciagle
):
    orig_pbn_client = Uczelnia.pbn_client

    try:
        pbn_client = mocker.Mock()

        Uczelnia.pbn_client = pbn_client

        uczelnia.pbn_aktualizuj_na_biezaco = False
        uczelnia.pbn_integracja = True
        uczelnia.save()

        url = "admin:bpp_wydawnictwo_ciagle_change"
        page = admin_app.get(reverse(url, args=(wydawnictwo_ciagle.pk,)))
        assert "Zapisz i wyślij do PBN" not in normalize_html(
            page.content.decode("utf-8")
        )
    finally:
        Uczelnia.pbn_client = orig_pbn_client


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
def test_Wydawnictwo_Ciagle_Admin_sprawdz_duplikaty_www_doi_pbn(
    admin_app, zrodlo, fld, value
):
    if fld == "pbn_uid":
        value = baker.make(Publication, pk=TEST_PBN_ID)

    baker.make(Wydawnictwo_Ciagle, **{fld: value})
    w2 = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)

    if fld == "pbn_uid":
        value = TEST_PBN_ID  # baker.make(Publication, pk=TEST_PBN_ID)

    url = "admin:bpp_wydawnictwo_ciagle_change"
    page = admin_app.get(reverse(url, args=(w2.pk,)))

    if fld == "pbn_uid":
        page.forms["wydawnictwo_ciagle_form"][fld].force_value(value)
    else:
        page.forms["wydawnictwo_ciagle_form"][fld].value = value
    res = page.forms["wydawnictwo_ciagle_form"].submit().maybe_follow()

    assert "inne rekordy z identycznym polem" in normalize_html(
        res.content.decode("utf-8")
    )


def test_Wydawnictwo_Ciagle_Autor_Admin_forwarding_works(
    admin_browser,
    wydawnictwo_ciagle,
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

    wydawnictwo_ciagle.rok = rok
    wydawnictwo_ciagle.save()

    aj = wydawnictwo_ciagle.dodaj_autora(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
    )

    url = (
        f"/admin/bpp/wydawnictwo_ciagle_autor/{aj.pk}/change/"
        f"?_changelist_filters=rekord__id__exact%3D{wydawnictwo_ciagle.pk}"
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
