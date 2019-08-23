import pytest
from django.urls import reverse

from bpp.models import Autor_Dyscyplina
from bpp.tests import select_select2_autocomplete
from django_bpp.selenium_util import wait_for


@pytest.mark.parametrize(
    "url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"]
)
def test_podpowiedzi_dyscyplin_autor_ma_dwie(
        url, live_server, preauth_admin_browser, autor_jan_kowalski, dyscyplina1, dyscyplina2):
    Autor_Dyscyplina.objects.create(rok=2018, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1,
                                    subdyscyplina_naukowa=dyscyplina2)
    url = reverse("admin:bpp_%s_add" % url)
    preauth_admin_browser.visit(live_server + url)

    preauth_admin_browser.type("rok", "2018")

    preauth_admin_browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[0].scrollIntoView()
    """)

    preauth_admin_browser.find_by_css(".grp-add-handler").first.click()
    wait_for(
        lambda: preauth_admin_browser.find_by_id("id_autorzy_set-0-autor")
    )
    select_select2_autocomplete(
        preauth_admin_browser,
        "id_autorzy_set-0-autor",
        "KOWALSKI"
    )

    sel = preauth_admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.value == "---------"


@pytest.mark.parametrize(
    "url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"]
)
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_podpowiada(
        url, live_server, preauth_admin_browser, autor_jan_kowalski, dyscyplina1, dyscyplina2, uczelnia):
    uczelnia.podpowiadaj_dyscypliny = True
    uczelnia.save()

    Autor_Dyscyplina.objects.create(rok=2018, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1)
    url = reverse("admin:bpp_%s_add" % url)
    preauth_admin_browser.visit(live_server + url)

    preauth_admin_browser.type("rok", "2018")

    preauth_admin_browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[0].scrollIntoView()
    """)

    preauth_admin_browser.find_by_css(".grp-add-handler").first.click()
    wait_for(
        lambda: preauth_admin_browser.find_by_id("id_autorzy_set-0-autor")
    )
    select_select2_autocomplete(
        preauth_admin_browser,
        "id_autorzy_set-0-autor",
        "KOWALSKI"
    )

    sel = preauth_admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert int(sel.value) == dyscyplina1.pk


@pytest.mark.parametrize(
    "url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"]
)
def test_podpowiedzi_dyscyplin_autor_ma_jedna_uczelnia_nie_podpowiada(
        url, live_server, preauth_admin_browser, autor_jan_kowalski, dyscyplina1, dyscyplina2, uczelnia):
    uczelnia.podpowiadaj_dyscypliny = False
    uczelnia.save()

    Autor_Dyscyplina.objects.create(rok=2018, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1)
    url = reverse("admin:bpp_%s_add" % url)
    preauth_admin_browser.visit(live_server + url)

    preauth_admin_browser.type("rok", "2018")

    preauth_admin_browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[0].scrollIntoView()
    """)

    preauth_admin_browser.find_by_css(".grp-add-handler").first.click()
    wait_for(
        lambda: preauth_admin_browser.find_by_id("id_autorzy_set-0-autor")
    )
    select_select2_autocomplete(
        preauth_admin_browser,
        "id_autorzy_set-0-autor",
        "KOWALSKI"
    )

    sel = preauth_admin_browser.find_by_id("id_autorzy_set-0-dyscyplina_naukowa")
    assert sel.value == "---------"
