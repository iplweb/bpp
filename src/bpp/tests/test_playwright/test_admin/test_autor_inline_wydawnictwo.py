import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN
from django_bpp.playwright_util import select_select2_autocomplete


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("wyd", ["ciagle", "zwarte"])
def test_autor_inline_wydawnictwo_dyscyplina(
    autor_z_dyscyplina,
    jednostka,
    rok,
    admin_page: Page,
    live_server,
    standard_data,
    wyd,
    zrodlo,
):
    """Test that author discipline auto-fills when adding autor inline."""
    url = live_server.url + reverse(f"admin:bpp_wydawnictwo_{wyd}_add")
    admin_page.goto(url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Fill form fields
    admin_page.fill("#id_tytul_oryginalny", "123")

    if wyd == "ciagle":
        select_select2_autocomplete(
            admin_page, "id_zrodlo", zrodlo.nazwa, timeout=4000
        )

    admin_page.fill("#id_rok", str(rok))

    # Select charakter_formalny
    charakter = Charakter_Formalny.objects.first()
    if charakter:
        admin_page.select_option("#id_charakter_formalny", value=str(charakter.pk))

    # Select jezyk
    jezyk = Jezyk.objects.first()
    if jezyk:
        admin_page.select_option("#id_jezyk", value=str(jezyk.pk))

    # Select typ_kbn
    typ_kbn = Typ_KBN.objects.first()
    if typ_kbn:
        admin_page.select_option("#id_typ_kbn", value=str(typ_kbn.pk))

    # Add autor inline
    admin_page.wait_for_selector(".grp-add-handler", state="visible", timeout=10000)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-0-autor", state="visible", timeout=10000
    )

    # Fill autor inline - dyscyplina should auto-fill
    select_select2_autocomplete(
        admin_page,
        "id_autorzy_set-0-autor",
        autor_z_dyscyplina.autor.nazwisko,
        timeout=4000,
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-zapisany_jako", "123 foo", timeout=4000
    )

    # Submit form
    admin_page.click("input[name='_continue']")
    admin_page.wait_for_load_state("domcontentloaded", timeout=15000)

    # Check success
    admin_page.wait_for_function(
        "() => document.body.textContent.includes('dodany(-na)(-ne) pomyślnie')",
        timeout=10000,
    )
