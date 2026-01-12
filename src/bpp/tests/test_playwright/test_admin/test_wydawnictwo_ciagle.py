import pytest
from playwright.sync_api import Page

from bpp.models import Autor_Dyscyplina
from django_bpp.playwright_util import select_select2_autocomplete


@pytest.mark.django_db(transaction=True)
def test_Wydawnictwo_Ciagle_Autor_Admin_forwarding_works(
    admin_page: Page,
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    dyscyplina1,
    jednostka,
    live_server,
):
    """Test editing Wydawnictwo_Ciagle_Autor inline with discipline selection."""
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

    admin_page.goto(live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Wait for the page to be fully loaded (rok field is hidden type=hidden)
    admin_page.wait_for_selector("#id_rok", state="attached", timeout=10000)

    # Select discipline using Select2 autocomplete
    select_select2_autocomplete(
        admin_page, "id_dyscyplina_naukowa", dyscyplina1.nazwa, timeout=4000
    )

    # Submit form
    admin_page.click("input[type='submit'].grp-default")
    admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

    # Wait for success message
    admin_page.wait_for_function(
        "() => document.body.textContent.includes('pomyślnie')",
        timeout=10000,
    )

    aj.refresh_from_db()

    assert aj.dyscyplina_naukowa.pk == dyscyplina1.pk
