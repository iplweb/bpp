import pytest
from django.urls import reverse

from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN
from bpp.tests import (
    add_extra_autor_inline,
    fill_admin_inline,
    select_select2_autocomplete,
    show_element,
)

from django_bpp.selenium_util import wait_for_page_load


@pytest.mark.parametrize("wyd", ["ciagle", "zwarte"])
def test_autor_inline_wydawnictwo_dyscyplina(
    autor_z_dyscyplina,
    jednostka,
    rok,
    admin_browser,
    live_server,
    standard_data,
    wyd,
    zrodlo,
):
    url = reverse(f"admin:bpp_wydawnictwo_{wyd}_add")
    admin_browser.visit(live_server + url)

    admin_browser.type("tytul_oryginalny", "123")
    if wyd == "ciagle":
        select_select2_autocomplete(admin_browser, "id_zrodlo", zrodlo.nazwa)
    admin_browser.type("rok", str(rok))

    show_element(admin_browser, admin_browser.find_by_name("charakter_formalny"))
    admin_browser.select("charakter_formalny", Charakter_Formalny.objects.first().pk)
    admin_browser.select("jezyk", Jezyk.objects.first().pk)
    show_element(admin_browser, admin_browser.find_by_name("typ_kbn"))
    admin_browser.select("typ_kbn", Typ_KBN.objects.first().pk)

    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor_z_dyscyplina.autor,
        jednostka,
        "123 foo",
        dyscyplina=autor_z_dyscyplina.dyscyplina_naukowa,
    )

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_continue").click()

    assert "dodany pomyślnie" in admin_browser.html
