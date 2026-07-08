import pytest
from playwright.sync_api import Page

from bpp.models import Autor_Dyscyplina
from django_bpp.playwright_util import select_select2_autocomplete


@pytest.mark.django_db(transaction=True)
def test_Wydawnictwo_Zwarte_Autor_Admin_forwarding_works(
    admin_page: Page,
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    dyscyplina1,
    jednostka,
    channels_live_server,
):
    rok = 2022

    # Defensywny guard: baseline lub wcześniejszy test mógł zostawić wiersze
    # Autor_Dyscyplina — czyścimy, by poniższy create dał deterministyczny
    # stan (mirror toz/tamze).
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

    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Wait for rok field to exist (it's a hidden input, so we don't check visibility)
    admin_page.wait_for_selector("[name='rok']", state="attached")

    select_select2_autocomplete(
        admin_page, "id_dyscyplina_naukowa", dyscyplina1.nazwa, timeout=30000
    )

    # Submit form. Zapis przekierowuje na changelist — blokujemy do
    # zakończenia nawigacji, żeby kolejne waity nie wracały od razu na
    # STAREJ stronie (race z domcontentloaded).
    with admin_page.expect_navigation(wait_until="domcontentloaded"):
        admin_page.click("input[type=submit][name='_save']")

    # Check success message
    admin_page.wait_for_function(
        "() => document.body.textContent.includes('pomyślnie')", timeout=10000
    )

    aj.refresh_from_db()

    assert aj.dyscyplina_naukowa.pk == dyscyplina1.pk
