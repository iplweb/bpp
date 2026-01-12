import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.models import Autor_Dyscyplina
from django_bpp.playwright_util import select_select2_autocomplete


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_dwie(
    url,
    channels_live_server,
    admin_page: Page,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
):
    Autor_Dyscyplina.objects.create(
        rok=2018,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )
    url = reverse("admin:bpp_%s_add" % url)
    admin_page.goto(channels_live_server.url + url)
    admin_page.fill('input[name="rok"]', "2018")

    # Click the "add author" button (grp-add-handler)
    admin_page.locator(".grp-add-handler").first.click()

    # Wait for the autor field to appear
    admin_page.wait_for_selector("#id_autorzy_set-0-autor", state="visible")

    # Select KOWALSKI in the autor field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", "KOWALSKI", timeout=30000
    )

    # Give time for any AJAX updates
    admin_page.wait_for_timeout(1000)

    # Check that dyscyplina_naukowa field has "---------" (no auto-fill)
    sel = admin_page.locator("#id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.input_value() == ""  # Empty value means "---------" is selected


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_nie_podpowiada(
    url,
    channels_live_server,
    admin_page: Page,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    uczelnia,
):
    uczelnia.podpowiadaj_dyscypliny = False
    uczelnia.save()

    Autor_Dyscyplina.objects.create(
        rok=2018, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )
    url = reverse("admin:bpp_%s_add" % url)
    admin_page.goto(channels_live_server.url + url)
    admin_page.fill('input[name="rok"]', "2018")

    # Click the "add author" button (grp-add-handler)
    admin_page.locator(".grp-add-handler").first.click()

    # Wait for the autor field to appear
    admin_page.wait_for_selector("#id_autorzy_set-0-autor", state="visible")

    # Select KOWALSKI in the autor field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", "KOWALSKI", timeout=30000
    )

    # Give time for any AJAX updates
    admin_page.wait_for_timeout(1000)

    # Check that dyscyplina_naukowa field has empty value (no auto-fill)
    sel = admin_page.locator("#id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.input_value() == ""


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_podpowiada(
    url,
    channels_live_server,
    admin_page: Page,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    uczelnia,
):
    uczelnia.podpowiadaj_dyscypliny = True
    uczelnia.save()

    Autor_Dyscyplina.objects.create(
        rok=2018, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )
    url = reverse("admin:bpp_%s_add" % url)
    admin_page.goto(channels_live_server.url + url)
    admin_page.fill('input[name="rok"]', "2018")

    # Click the "add author" button (grp-add-handler)
    admin_page.locator(".grp-add-handler").first.click()

    # Wait for the autor field to appear
    admin_page.wait_for_selector("#id_autorzy_set-0-autor", state="visible")

    # Select KOWALSKI in the autor field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", "KOWALSKI", timeout=30000
    )

    # Wait for discipline auto-fill to complete
    admin_page.wait_for_function(
        f"""() => {{
            const elem = document.querySelector('#id_autorzy_set-0-dyscyplina_naukowa');
            return elem && elem.value === '{dyscyplina1.pk}';
        }}""",
        timeout=10000,
    )

    # Verify the discipline was auto-filled
    sel = admin_page.locator("#id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.input_value() == str(dyscyplina1.pk)
