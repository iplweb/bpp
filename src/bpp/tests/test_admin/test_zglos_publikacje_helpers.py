from unittest.mock import Mock

import pytest
from django.urls import reverse

from bpp.admin.zglos_publikacje_helpers import (
    KorzystaZNumeruZgloszeniaInlineMixin,
    KorzystaZNumeruZgloszeniaMixin,
    UzupelniajWstepneDanePoNumerzeZgloszeniaMixin,
)
from bpp.const import NUMER_ZGLOSZENIA_PARAM


def test_KorzystaZNumeruZgloszeniaMixin(zgloszenie_publikacji, rf):
    req = rf.get("/", {NUMER_ZGLOSZENIA_PARAM: zgloszenie_publikacji.pk})
    assert (
        KorzystaZNumeruZgloszeniaMixin.get_zgloszenie_publikacji(None, req)
        == zgloszenie_publikacji
    )


def test_KorzystaZNumeruZgloszeniaInlineMixin(zgloszenie_publikacji, rf):

    req = rf.get("/", {NUMER_ZGLOSZENIA_PARAM: zgloszenie_publikacji.pk})
    assert KorzystaZNumeruZgloszeniaInlineMixin().get_extra(req) == 1

    zgloszenie_publikacji.zgloszenie_publikacji_autor_set.all().delete()
    req = rf.get("/", {NUMER_ZGLOSZENIA_PARAM: zgloszenie_publikacji.pk})
    assert KorzystaZNumeruZgloszeniaInlineMixin().get_extra(req) == 0


def test_WstepneDanePoNumerzeZgloszeniaMixin_get_changeform_initial_data(
    zgloszenie_publikacji, rf, rok
):
    req = rf.get("/", {NUMER_ZGLOSZENIA_PARAM: zgloszenie_publikacji.pk})
    ret = UzupelniajWstepneDanePoNumerzeZgloszeniaMixin().get_changeform_initial_data(
        req
    )
    assert str(ret["rok"]) == str(rok)


def test_WstepneDanePoNumerzeZgloszeniaMixin_get_formset_kwargs(
    zgloszenie_publikacji, rf, rok
):
    class baseModel_AutorInline:
        pass

    req = rf.get("/", {NUMER_ZGLOSZENIA_PARAM: zgloszenie_publikacji.pk})
    ret = UzupelniajWstepneDanePoNumerzeZgloszeniaMixin().get_formset_kwargs(
        request=req,
        obj=Mock(pk=None),
        inline=baseModel_AutorInline(),
        prefix="autorzy_set",
    )
    assert (
        ret["initial"][0]["autor"]
        == zgloszenie_publikacji.zgloszenie_publikacji_autor_set.first().autor.pk
    )


@pytest.mark.parametrize(["url"], [("wydawnictwo_ciagle",), ("wydawnictwo_zwarte",)])
def test_integracyjny_strona_admina(admin_app, zgloszenie_publikacji, url):
    url = (
        reverse(f"admin:bpp_{url}_add")
        + f"?{NUMER_ZGLOSZENIA_PARAM}={zgloszenie_publikacji.pk}"
    )
    page = admin_app.get(url)

    assert page.forms[1]["autorzy_set-0-autor"].value == str(
        zgloszenie_publikacji.zgloszenie_publikacji_autor_set.first().autor.pk
    )


@pytest.mark.parametrize(["url"], [("wydawnictwo_ciagle",), ("wydawnictwo_zwarte",)])
def test_integracyjny_admin_czy_oplaty_przechodza(
    admin_app, zgloszenie_publikacji_z_oplata, url
):
    url = (
        reverse(f"admin:bpp_{url}_add")
        + f"?{NUMER_ZGLOSZENIA_PARAM}={zgloszenie_publikacji_z_oplata.pk}"
    )
    page = admin_app.get(url)
    assert (
        page.forms[1]["opl_pub_amount"].value
        == str(zgloszenie_publikacji_z_oplata.opl_pub_amount) + ".00"
    )
    assert page.forms[1]["opl_pub_cost_free"].value == "false"


@pytest.mark.parametrize(["url"], [("wydawnictwo_ciagle",), ("wydawnictwo_zwarte",)])
def test_integracyjny_admin_czy_public_dostep_dnia_ustawiony(
    admin_app, zgloszenie_publikacji, url
):
    url = (
        reverse(f"admin:bpp_{url}_add")
        + f"?{NUMER_ZGLOSZENIA_PARAM}={zgloszenie_publikacji.pk}"
    )
    page = admin_app.get(url)
    assert page.forms[1]["public_dostep_dnia"].value != ""
