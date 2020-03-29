import pytest
from django.urls import reverse
from selenium.common.exceptions import ElementClickInterceptedException

from bpp.models import Autor_Dyscyplina
from bpp.tests import select_select2_autocomplete
from django_bpp.selenium_util import wait_for


def scroll_until_handler_clicked_successfully(browser, handler="grp-add-handler"):
    browser.execute_script(
        'document.getElementsByClassName("%s")[0].scrollIntoView();' % handler
    )
    no_tries = 0
    while no_tries < 20:
        try:
            browser.find_by_css(".grp-add-handler").first.click()
            break
        except ElementClickInterceptedException:
            browser.execute_script("window.scrollBy(0, 25)")
        no_tries += 1


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_dwie(
    url,
    nginx_live_server,
    preauth_admin_browser,
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
    preauth_admin_browser.visit(nginx_live_server.url + url)

    preauth_admin_browser.type("rok", "2018")

    scroll_until_handler_clicked_successfully(preauth_admin_browser)

    wait_for(lambda: preauth_admin_browser.find_by_id("id_autorzy_set-0-autor"))
    select_select2_autocomplete(
        preauth_admin_browser, "id_autorzy_set-0-autor", "KOWALSKI"
    )

    sel = preauth_admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.value == "---------"


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_podpowiada(
    url,
    nginx_live_server,
    preauth_admin_browser,
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
    preauth_admin_browser.visit(nginx_live_server.url + url)

    preauth_admin_browser.type("rok", "2018")

    scroll_until_handler_clicked_successfully(preauth_admin_browser)

    wait_for(lambda: preauth_admin_browser.find_by_id("id_autorzy_set-0-autor"))

    no_tries = 0

    while no_tries < 10:
        select_select2_autocomplete(
            preauth_admin_browser, "id_autorzy_set-0-autor", "KOWALSKI"
        )

        sel = preauth_admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")

        i = None
        try:
            i = int(sel.value)
        except:
            pass

        if i == dyscyplina1.pk:
            break

        no_tries += 1

    if no_tries == 10:
        assert False


@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_nie_podpowiada(
    url,
    nginx_live_server,
    preauth_admin_browser,
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
    preauth_admin_browser.visit(nginx_live_server.url + url)

    preauth_admin_browser.type("rok", "2018")

    scroll_until_handler_clicked_successfully(preauth_admin_browser)

    wait_for(lambda: preauth_admin_browser.find_by_id("id_autorzy_set-0-autor"))
    select_select2_autocomplete(
        preauth_admin_browser, "id_autorzy_set-0-autor", "KOWALSKI"
    )

    sel = preauth_admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.value == "---------"
