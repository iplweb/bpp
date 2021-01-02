import pytest
from django.urls import reverse
from selenium.webdriver.support.wait import WebDriverWait

from bpp.models import Autor_Dyscyplina
from bpp.tests import select_select2_autocomplete

from django_bpp.selenium_util import wait_for


def scroll_until_handler_clicked_successfully(browser, handler="grp-add-handler"):
    browser.execute_script(
        'document.getElementsByClassName("%s")[0].scrollIntoView();' % handler
    )
    browser.execute_script(
        'document.getElementsByClassName("%s")[0].click();' % handler
    )


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_dwie(
    url,
    asgi_live_server,
    admin_browser,
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
    admin_browser.visit(asgi_live_server.url + url)

    admin_browser.type("rok", "2018")

    scroll_until_handler_clicked_successfully(admin_browser)

    wait_for(lambda: admin_browser.find_by_id("id_autorzy_set-0-autor"))
    select_select2_autocomplete(admin_browser, "id_autorzy_set-0-autor", "KOWALSKI")

    sel = admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.value == "---------"


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_podpowiada(
    url,
    asgi_live_server,
    admin_browser,
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
    admin_browser.visit(asgi_live_server.url + url)

    admin_browser.type("rok", "2018")

    scroll_until_handler_clicked_successfully(admin_browser)

    wait_for(lambda: admin_browser.find_by_id("id_autorzy_set-0-autor"))

    select_select2_autocomplete(admin_browser, "id_autorzy_set-0-autor", "KOWALSKI")

    admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")

    WebDriverWait(admin_browser.driver, 10).until(
        lambda driver: admin_browser.find_by_id(
            "id_autorzy_set-0-dyscyplina_naukowa"
        ).value
        == str(dyscyplina1.pk)
    )


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_nie_podpowiada(
    url,
    asgi_live_server,
    admin_browser,
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
    admin_browser.visit(asgi_live_server.url + url)

    admin_browser.type("rok", "2018")

    scroll_until_handler_clicked_successfully(admin_browser)

    wait_for(lambda: admin_browser.find_by_id("id_autorzy_set-0-autor"))
    select_select2_autocomplete(admin_browser, "id_autorzy_set-0-autor", "KOWALSKI")

    sel = admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.value == "---------"
