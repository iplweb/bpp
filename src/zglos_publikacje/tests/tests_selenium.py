from django.urls import reverse

from bpp.models import Autor_Dyscyplina, Autor_Jednostka
from bpp.tests import proper_click_by_id, select_select2_autocomplete

from django_bpp.selenium_util import wait_for_page_load


def test_zglos_publikacje_drugi_autor_dyscyplina(
    admin_browser,
    live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_browser.visit(live_server.url + reverse("zglos_publikacje:nowe_zgloszenie"))

    admin_browser.fill("0-tytul_oryginalny", "test")
    admin_browser.select("0-rodzaj_zglaszanej_publikacji", "2")
    admin_browser.fill("0-strona_www", "https://www.onet.pl/")
    admin_browser.fill("0-rok", str(rok))
    admin_browser.fill("0-email", "moj@email.pl")
    with wait_for_page_load(admin_browser):
        proper_click_by_id(admin_browser, "id-wizard-submit")

    n = 1
    admin_browser.find_by_id("add-form").click()
    select_select2_autocomplete(admin_browser, f"id_2-{n}-autor", "Kowal")
    assert admin_browser.find_by_id(f"id_2-{n}-dyscyplina_naukowa").value == str(
        dyscyplina1.pk
    )


def test_zglos_publikacje_z_plikiem_drugi_autor_dyscyplina(
    admin_browser,
    live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_browser.visit(live_server.url + reverse("zglos_publikacje:nowe_zgloszenie"))

    admin_browser.fill("0-tytul_oryginalny", "test")
    admin_browser.select("0-rodzaj_zglaszanej_publikacji", "2")
    admin_browser.fill("0-rok", str(rok))
    admin_browser.fill("0-email", "moj@email.pl")
    with wait_for_page_load(admin_browser):
        proper_click_by_id(admin_browser, "id-wizard-submit")

    import os

    plik = os.path.abspath(os.path.join(os.path.dirname(__file__), "example.pdf"))
    admin_browser.fill("1-plik", plik)
    with wait_for_page_load(admin_browser):
        proper_click_by_id(admin_browser, "id-wizard-submit")

    n = 1
    admin_browser.find_by_id("add-form").click()
    select_select2_autocomplete(admin_browser, f"id_2-{n}-autor", "Kowal")
    assert admin_browser.find_by_id(f"id_2-{n}-dyscyplina_naukowa").value == str(
        dyscyplina1.pk
    )


def test_zglos_publikacje_wiele_klikniec_psuje_select2(
    admin_browser,
    live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_browser.visit(live_server.url + reverse("zglos_publikacje:nowe_zgloszenie"))

    admin_browser.fill("0-tytul_oryginalny", "test")
    admin_browser.select("0-rodzaj_zglaszanej_publikacji", "2")
    admin_browser.fill("0-strona_www", "https://www.onet.pl/")
    admin_browser.fill("0-rok", str(rok))
    admin_browser.fill("0-email", "moj@email.pl")
    with wait_for_page_load(admin_browser):
        proper_click_by_id(admin_browser, "id-wizard-submit")

    proper_click_by_id(admin_browser, "add-form")
    proper_click_by_id(admin_browser, "add-form")
    proper_click_by_id(admin_browser, "add-form")

    select_select2_autocomplete(admin_browser, "id_2-1-autor", "Kowal")
    assert admin_browser.find_by_id("id_2-1-dyscyplina_naukowa").value == str(
        dyscyplina1.pk
    )


def test_zglos_publikacje_z_plikiem_wiele_klikniec_psuje_select2(
    admin_browser,
    live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_browser.visit(live_server.url + reverse("zglos_publikacje:nowe_zgloszenie"))

    admin_browser.fill("0-tytul_oryginalny", "test")
    admin_browser.select("0-rodzaj_zglaszanej_publikacji", "2")
    admin_browser.fill("0-rok", str(rok))
    admin_browser.fill("0-email", "moj@email.pl")
    with wait_for_page_load(admin_browser):
        proper_click_by_id(admin_browser, "id-wizard-submit")

    import os

    plik = os.path.abspath(os.path.join(os.path.dirname(__file__), "example.pdf"))
    admin_browser.fill("1-plik", plik)
    with wait_for_page_load(admin_browser):
        proper_click_by_id(admin_browser, "id-wizard-submit")

    proper_click_by_id(admin_browser, "add-form")
    proper_click_by_id(admin_browser, "add-form")
    proper_click_by_id(admin_browser, "add-form")

    select_select2_autocomplete(admin_browser, "id_2-1-autor", "Kowal")
    assert admin_browser.find_by_id("id_2-1-dyscyplina_naukowa").value == str(
        dyscyplina1.pk
    )
