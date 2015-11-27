# -*- encoding: utf-8 -*-
import time

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.patent import Patent
from bpp.models.system import Status_Korekty
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import any_ciagle, any_autor, any_jednostka
from bpp.tests.helpers import SeleniumLoggedInAdminTestCase
from bpp.tests.util import any_zrodlo, CURRENT_YEAR, any_zwarte, any_patent


ID = "id_tytul_oryginalny"

def scrollIntoView(browser, arg):
    return browser.execute_script("document.getElementById('id_" + arg + "').scrollIntoView()")

def proper_click(browser, arg):
    browser.execute_script("document.getElementById('id_" + arg + "').scrollIntoView()")
    browser.execute_script("document.getElementById('id_" + arg + "').click()")

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

    c = any_ciagle(informacje='TO INFORMACJE')

    preauth_admin_browser.visit(live_server + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,)))

    wcc = Wydawnictwo_Ciagle.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id('toz')
    toz.click()

    assertPopupContains(preauth_admin_browser, u"Utworzysz kopię tego rekordu")
    assert preauth_admin_browser.is_element_present_by_id('navigation-menu', wait_time=5000)

    assert wcc() == 2

def test_admin_wydawnictwo_zwarte_toz(preauth_admin_browser, live_server):
    c = any_zwarte(informacje="TO INFOMRACJE")

    preauth_admin_browser.visit(live_server + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,)))

    wcc = Wydawnictwo_Zwarte.objects.count
    assert wcc() == 1

    toz = preauth_admin_browser.find_by_id('toz')
    toz.click()

    assertPopupContains(preauth_admin_browser, u"Utworzysz kopię tego rekordu")
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

    assertPopupContains(preauth_admin_browser, u"Utworzysz kopię tego rekordu")
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

def test_automatycznie_uzupelnij_punkty(preauth_admin_browser, live_server):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    preauth_admin_browser.visit(live_server + url)

    z = any_zrodlo(nazwa="FOO BAR")

    preauth_admin_browser.execute_script("$('#id_wypelnij_pola_punktacji_button').click()")
    assertPopupContains(preauth_admin_browser, u"Najpierw wybierz jakie")
    time.sleep(1)

    zrodlo = preauth_admin_browser.find_by_id("id_zrodlo-autocomplete")
    zrodlo.type("FOO BAR")
    time.sleep(2)
    zrodlo.type(Keys.TAB)

    preauth_admin_browser.execute_script("$('#id_wypelnij_pola_punktacji_button').click()")
    assertPopupContains(preauth_admin_browser, u"Uzupełnij pole")



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
    time.sleep(1)

    assert rok.value == str(CURRENT_YEAR)
    assert punkty_kbn.value == "5.00"

    proper_click(preauth_admin_browser, "wypelnij_pola_punktacji_button")
    time.sleep(1)

    assert punkty_kbn.value == "10.20"
    button = preauth_admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    assert button.value == u"Wypełniona!"

    trigger_event(rok, "change")
    time.sleep(1)
    # Po zmianie roku LUB źródła przycisk ma się zmienić
    assert button.value ==  u"Wypełnij pola punktacji"

    # Zwiększymy rok o 1 i sprawdzimy, czy zmieni się punktacja
    rok.value = str(CURRENT_YEAR + 1)

    proper_click(preauth_admin_browser, "wypelnij_pola_punktacji_button")
    time.sleep(1)

    assert punkty_kbn.value == "11.20"

    # Teraz usuniemy źródło i sprawdzimy, czy przycisk zmieni nazwę
    button.value == u"Wypełniona!"
    preauth_admin_browser.execute_script('$("span.remove").first().click()')
    time.sleep(1)

    button = preauth_admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    assert button.value == u"Wypełnij pola punktacji"



#
# class SeleniumAdminTestUploadujPunkty(
#     ProperClickMixin, SeleniumLoggedInAdminTestCase):
#     url = reverse("admin:bpp_wydawnictwo_ciagle_add")
#
#     def setUp(self):
#         self.z = any_zrodlo(nazwa="WTF LOL")
#         SeleniumLoggedInAdminTestCase.setUp(self)
#
#     def test_upload_punkty(self):
#
#         byId = self.byId
#
#         z = self.z
#
#         byId("zrodlo-autocomplete").send_keys("WTF LOL")
#         time.sleep(2)
#         byId("zrodlo-autocomplete").send_keys(Keys.TAB)
#         byId("rok").send_keys(str(CURRENT_YEAR))
#         byId("impact_factor").val("50")
#
#         self.proper_click("dodaj_punktacje_do_zrodla_button")
#         time.sleep(2)
#
#         self.assertEquals(Punktacja_Zrodla.objects.count(), 1)
#         self.assertEquals(Punktacja_Zrodla.objects.all()[0].impact_factor, 50)
#
#         byId("impact_factor").val("60")
#         self.proper_click("dodaj_punktacje_do_zrodla_button")
#         time.sleep(2)
#         self.page.assertPopupContains(u"Punktacja dla tego roku już istnieje")
#         time.sleep(2)
#
#         self.assertEquals(Punktacja_Zrodla.objects.count(), 1)
#         self.assertEquals(Punktacja_Zrodla.objects.all()[0].impact_factor, 60)
#
#
# class SeleniumAdminTestAutorformJednostka(SeleniumLoggedInAdminTestCase):
#     url = reverse("admin:bpp_wydawnictwo_ciagle_add")
#
#     def setUp(self):
#         with transaction.atomic():
#             a = any_autor(nazwisko="KOWALSKI", imiona="Jan Sebastian")
#             j = any_jednostka(nazwa="WTF LOL")
#             j.dodaj_autora(a)
#         SeleniumLoggedInAdminTestCase.setUp(self)
#
#     def test_bug_wydawnictwo_ciagle_zapisz(self):
#         elem = self.page.find_element_by_name("_continue")
#         elem.click()
#         time.sleep(3)
#         self.assertIn("To pole jest wymagane.", self.page.page_source)
#
#     def test_uzupelnianie_jednostki(self):
#         aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-autor-autocomplete")
#         aut.send_keys("KOWALSKI")
#         time.sleep(2)
#         aut.send_keys(Keys.TAB)
#         time.sleep(2)
#
#         jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka"))
#         self.assertEquals(
#             jed.first_selected_option.text(),
#             "WTF LOL")
#
#     def test_uzupelnianie_jednostki_drugi_wiersz(self):
#         # bug polegający na tym, że druga jednostka się ŹLE wypełnia
#
#         # najpierw kliknij "dodaj autora"
#         self.page.execute_script('$(".grp-add-handler")[1].click()')
#         time.sleep(2)
#
#         # a potem wpisz dane i sprawdź, że jednostki NIE będzie
#
#         aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-1-autor-autocomplete")
#         aut.send_keys("KOWALSKI")
#         time.sleep(2)
#         aut.send_keys(Keys.TAB)
#         time.sleep(2)
#
#         jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-1-jednostka"))
#         self.assertEquals(
#             jed.first_selected_option.text(),
#             "WTF LOL")
#
#
#     def test_kasowanie_autora(self):
#         # bug polegający na tym, że przy dodaniu autora i potem skasowaniu go,
#         # pole jednostki i nazwisk się NIE czyści
#         # ... ale zostawiam to w spokoju.
#         # bo: 1) trudno zlapac event czyszczenia pola ( d-a-light zmienia chyba DOM)
#         #     2) co to niby ma dać?
#         #     3) ten test zostaje, bo sprawdza działanie przycisku 'remove' - był bug na to
#
#         aut = self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-autor-autocomplete")
#         aut.send_keys("KOWALSKI")
#         time.sleep(2)
#         aut.send_keys(Keys.TAB)
#         time.sleep(2)
#
#         self.page.execute_script("""
#         $("#id_wydawnictwo_ciagle_autor_set-0-autor-deck").find(".remove").click()
#         """)
#
#         jed = Select(self.page.find_element_by_id("id_wydawnictwo_ciagle_autor_set-0-jednostka"))
#         self.assertEquals(jed.first_selected_option.text(), "WTF LOL")
#

def test_bug_on_user_add(preauth_admin_browser, live_server):
    preauth_admin_browser.visit(live_server + reverse('admin:bpp_bppuser_add'))
    preauth_admin_browser.find_by_id("id_username").send_keys("as")
    preauth_admin_browser.find_by_id("id_password1").send_keys("as")
    preauth_admin_browser.find_by_id("id_password2").send_keys("as")
    preauth_admin_browser.find_by_name("_continue").click()
    time.sleep(3)
    assert "server error" not in preauth_admin_browser.html
    assert u"Zmień użytkownik" in preauth_admin_browser.html
