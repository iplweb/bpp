from django.urls import reverse
from model_mommy import mommy

from pbn_api.models import Publication, SentData

from bpp.models import Uczelnia, const
from bpp.tests import normalize_html


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

        pub = mommy.make(Publication)
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
