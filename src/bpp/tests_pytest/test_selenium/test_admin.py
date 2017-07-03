# -*- encoding: utf-8 -*-
import time

import pytest
from django.core.urlresolvers import reverse
from django.db import transaction
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import any_ciagle, any_autor, any_jednostka
from bpp.tests.util import any_zrodlo, CURRENT_YEAR, any_zwarte, any_patent, \
    select_select2_autocomplete, scroll_into_view, \
    select_select2_clear_selection
from django_bpp.selenium_util import wait_for_page_load, wait_for

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def proper_click(browser, arg):
    # Czy ta metoda jest potrzebna? Kiedyś był bug, który
    # uniemożliwiał kliknięcie elementu, który nei był widoczny
    # na stronie, stąd konieczność przescrollowania do niego
    scroll_into_view(browser, arg)
    browser.execute_script("document.getElementById('" + arg + "').click()")


def clickButtonBuggyMarionetteDriver(browser, id):
    try:
        browser.execute_script("$('#" + id + "').click()")
    except WebDriverException as e:
        if e.msg.startswith("Failed to find value field"):
            pass
        else:
            raise e


# url = "/admin/"

def assertPopupContains(browser, text, accept=True):
    """Switch to popup, assert it contains at least a part
    of the text, close the popup. Error otherwise.
    """
    alert = browser.driver.switch_to.alert
    if text not in alert.text:
        raise AssertionError("%r not found in %r" % (text, alert.text))
    if accept:
        alert.accept()


def test_admin_wydawnictwo_ciagle_toz(preauth_admin_browser, live_server):
    Wydawnictwo_Ciagle.objects.all().delete()
    c = any_ciagle(informacje='TO INFORMACJE')

    preauth_admin_browser.visit(live_server + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,)))

    wcc = Wydawnictwo_Ciagle.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id('toz')
    toz.click()

    assertPopupContains(preauth_admin_browser, "Utworzysz kopię tego rekordu")
    time.sleep(2)
    assert preauth_admin_browser.is_element_present_by_id('navigation-menu', wait_time=5000)

    assert wcc() == 2


def test_admin_wydawnictwo_zwarte_toz(preauth_admin_browser, live_server):
    c = any_zwarte(informacje="TO INFOMRACJE")

    preauth_admin_browser.visit(live_server + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,)))

    wcc = Wydawnictwo_Zwarte.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id('toz')
    toz.click()

    assertPopupContains(preauth_admin_browser, "Utworzysz kopię tego rekordu")
    time.sleep(2)
    preauth_admin_browser.is_element_present_by_id('navigation-menu', 5000)
    assert wcc() == 2


def test_admin_wydawnictwo_ciagle_tamze(preauth_admin_browser, live_server):
    c = any_ciagle(informacje='TO INFORMACJE', uwagi='te uwagi', www='te www')
    preauth_admin_browser.visit(live_server + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,)))

    tamze = preauth_admin_browser.find_by_id('tamze')
    tamze.click()
    time.sleep(1)
    assert 'Dodaj wydawnictwo' in preauth_admin_browser.html

    for elem in ['TO INFORMACJE', 'te uwagi', 'te www']:
        assert elem in preauth_admin_browser.html, 'BRAK %r' % elem


def test_admin_wydawnictwo_zwarte_tamze(preauth_admin_browser, live_server):
    c = any_zwarte(
        informacje="TO INFORMACJE",
        uwagi='te uwagi',
        miejsce_i_rok='te miejsce i rok',
        wydawnictwo='te wydawnictwo',
        www='ten adres WWW',
        isbn='Z_ISBN',
        e_isbn='E_ISBN')
    preauth_admin_browser.visit(live_server + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,)))

    tamze = preauth_admin_browser.find_by_id('tamze')
    tamze.click()
    time.sleep(1)
    assert 'Dodaj wydawnictwo' in preauth_admin_browser.html
    for elem in ['TO INFORMACJE', 'te uwagi', 'te miejsce i rok',
                 'te wydawnictwo', 'ten adres WWW', 'Z_ISBN', 'E_ISBN']:
        assert elem in preauth_admin_browser.html, 'BRAK %r' % elem


def test_admin_patent_toz(preauth_admin_browser, live_server):
    c = any_patent(informacje="TO INFORMACJE")
    preauth_admin_browser.visit(live_server + reverse("admin:bpp_patent_change", args=(c.pk,)))

    wcc = Patent.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id('toz')
    toz.click()

    assertPopupContains(preauth_admin_browser, "Utworzysz kopię tego rekordu")
    time.sleep(2)

    preauth_admin_browser.is_element_present_by_id('navigation-menu', 5000)
    assert wcc() == 2


def test_admin_patent_tamze(preauth_admin_browser, live_server):
    c = any_patent(informacje="TO INFORMACJE")
    preauth_admin_browser.visit(live_server + reverse("admin:bpp_patent_change", args=(c.pk,)))

    tamze = preauth_admin_browser.find_by_id('tamze')
    tamze.click()
    time.sleep(1)
    assert 'Dodaj patent' in preauth_admin_browser.html
    assert 'TO INFORMACJE' in preauth_admin_browser.html

@pytest.mark.django_db(transaction=True)
def test_automatycznie_uzupelnij_punkty(preauth_admin_browser, live_server):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    preauth_admin_browser.visit(live_server + url)

    z = any_zrodlo(nazwa="FOO BAR")
    clickButtonBuggyMarionetteDriver(
        preauth_admin_browser,
        "id_wypelnij_pola_punktacji_button")
    assertPopupContains(preauth_admin_browser, "Najpierw wybierz jakie")

    select_select2_autocomplete(
        preauth_admin_browser,
        "id_zrodlo",
        "FOO"
    )

    clickButtonBuggyMarionetteDriver(
        preauth_admin_browser,
        "id_wypelnij_pola_punktacji_button")
    assertPopupContains(preauth_admin_browser, "Uzupełnij pole")

    preauth_admin_browser.execute_script("window.onbeforeunload = function(e) {};")


def trigger_event(elem, event):
    # import pytest; pytest.set_trace()e
    elem.parent.driver.execute_script(
        "return $(arguments[0]).trigger(arguments[1]).get();",
        "#" + elem['id'], event)


def test_admin_uzupelnij_punkty(preauth_admin_browser, live_server):
    z = any_zrodlo(nazwa="WTF LOL")

    kw = dict(zrodlo=z)
    f = Punktacja_Zrodla.objects.create
    f(impact_factor=10.1, punkty_kbn=10.2, rok=CURRENT_YEAR, **kw)
    f(impact_factor=11.1, punkty_kbn=11.2, rok=CURRENT_YEAR + 1, **kw)

    c = any_ciagle(zrodlo=z, impact_factor=5, punkty_kbn=5)

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    preauth_admin_browser.visit(live_server + url)

    rok = preauth_admin_browser.find_by_id("id_rok")
    punkty_kbn = preauth_admin_browser.find_by_id("id_punkty_kbn")

    assert rok.value == str(CURRENT_YEAR)
    assert punkty_kbn.value == "5.00"

    proper_click(preauth_admin_browser, "id_wypelnij_pola_punktacji_button")
    time.sleep(1)

    assert punkty_kbn.value == "10.20"
    button = preauth_admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    assert button.value == "Wypełniona!"

    trigger_event(rok, "change")
    time.sleep(1)
    # Po zmianie roku LUB źródła przycisk ma się zmienić
    assert button.value == "Wypełnij pola punktacji"

    # Zwiększymy rok o 1 i sprawdzimy, czy zmieni się punktacja
    preauth_admin_browser.fill("rok", str(CURRENT_YEAR + 1))

    proper_click(preauth_admin_browser, "id_wypelnij_pola_punktacji_button")
    time.sleep(1)

    assert punkty_kbn.value == "11.20"

    # Teraz usuniemy źródło i sprawdzimy, czy przycisk zmieni nazwę
    assert button.value == "Wypełniona!"

    select_select2_clear_selection(preauth_admin_browser, "id_zrodlo")
    button = preauth_admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    assert button.value == "Wypełnij pola punktacji"

    preauth_admin_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_upload_punkty(preauth_admin_browser, live_server):
    z = any_zrodlo(nazwa="WTF LOL")
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    preauth_admin_browser.visit(live_server + url)

    select_select2_autocomplete(
        preauth_admin_browser,
        "id_zrodlo",
        "WTF"
    )

    scroll_into_view(preauth_admin_browser, "id_rok")
    preauth_admin_browser.fill("rok", str(CURRENT_YEAR))

    scroll_into_view(preauth_admin_browser, "id_impact_factor")
    preauth_admin_browser.fill("impact_factor", "1")

    proper_click(preauth_admin_browser, "id_dodaj_punktacje_do_zrodla_button")
    # preauth_admin_browser.find_by_id("id_dodaj_punktacje_do_zrodla_button").click()
    time.sleep(2)

    assert Punktacja_Zrodla.objects.count() == 1
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 1

    preauth_admin_browser.fill("impact_factor", "2")
    proper_click(preauth_admin_browser, "id_dodaj_punktacje_do_zrodla_button")
    # preauth_admin_browser.find_by_id("id_dodaj_punktacje_do_zrodla_button").click()
    time.sleep(2)

    assertPopupContains(preauth_admin_browser, "Punktacja dla tego roku już istnieje")
    time.sleep(2)

    assert Punktacja_Zrodla.objects.count() == 1
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 2

    preauth_admin_browser.execute_script("window.onbeforeunload = function(e) {};")


@pytest.fixture
def autorform_jednostka(db):
    with transaction.atomic():
        a = any_autor(nazwisko="KOWALSKI", imiona="Jan Sebastian")
        j = any_jednostka(nazwa="WTF LOL")
        j.dodaj_autora(a)
    return j


@pytest.fixture
def autorform_browser(preauth_admin_browser, db, live_server):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.visit(live_server + url)

    preauth_admin_browser.execute_script("window.onbeforeunload = function(e) {};")
    return preauth_admin_browser


def test_autorform_uzupelnianie_jednostki(autorform_browser, autorform_jednostka):
    autorform_browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[0].scrollIntoView()
    """)
    autorform_browser.find_by_css(".grp-add-handler").first.click()
    wait_for(
        lambda: autorform_browser.find_by_id("id_wydawnictwo_ciagle_autor_set-0-autor")
    )

    select_select2_autocomplete(
        autorform_browser,
        "id_wydawnictwo_ciagle_autor_set-0-autor",
        "KOWALSKI"
    )

    sel = autorform_browser.find_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka")
    assert sel.value == str(autorform_jednostka.pk)



def find_autocomplete_widget(browser, id):
    for elem in browser.find_by_css(".yourlabs-autocomplete"):
        try:
            dii = elem['data-input-id']
        except KeyError:
            continue

        if dii == id:
            return elem


def test_autorform_kasowanie_autora(autorform_browser, autorform_jednostka):

    # kliknij "dodaj powiazanie autor-wydawnictwo"
    autorform_browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[0].scrollIntoView()
    """)
    autorform_browser.find_by_css(".grp-add-handler").first.click()
    wait_for(
        lambda: autorform_browser.find_by_id("id_wydawnictwo_ciagle_autor_set-0-autor")
    )

    # uzupełnij autora
    select_select2_autocomplete(
        autorform_browser,
        "id_wydawnictwo_ciagle_autor_set-0-autor",
        "KOW")

    start = time.time()
    while True:
        jed = autorform_browser.find_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka")
        if jed.value != '':
            break
        time.sleep(0.1)
        if time.time() - start >= 3:
            raise Exception("Timeout")

    # Jednostka ustawiona. Usuń autora:
    select_select2_clear_selection(
        autorform_browser,
        "id_wydawnictwo_ciagle_autor_set-0-autor")

    # jednostka nie jest wybrana
    jed = autorform_browser.find_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka")
    assert jed.value.find("\n") != -1

    autorform_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_bug_on_user_add(preauth_admin_browser, live_server):
    preauth_admin_browser.visit(live_server + reverse('admin:bpp_bppuser_add'))
    preauth_admin_browser.fill("username", "as")
    preauth_admin_browser.fill("password1", "as")
    preauth_admin_browser.fill("password2", "as")
    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_name("_continue").click()
    assert "Zmień użytkownik" in preauth_admin_browser.html
