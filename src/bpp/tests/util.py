# -*- encoding: utf-8 -*-

"""Ten moduł zawiera 'normalne', dla ludzi funkcje, które mogą być używane
do ustawiania testów."""
import random
import time
from datetime import datetime

from model_mommy import mommy
from selenium.webdriver.common.keys import Keys

from bpp.models import Tytul, Autor, Jednostka, Wydawnictwo_Ciagle, \
    Wydawnictwo_Zwarte, Zrodlo, Wydzial, Uczelnia, Praca_Habilitacyjna, \
    Praca_Doktorska, Typ_KBN, Jezyk, Charakter_Formalny, Patent
from bpp.models.cache import TupleField
from bpp.models.system import Status_Korekty


def setup_mommy():
    mommy.generators.add('django.contrib.postgres.fields.array.ArrayField',
                         lambda x: [])

    mommy.generators.add('django.contrib.postgres.search.SearchVectorField',
                         lambda x=None: None)



def set_default(varname, value, dct):
    if varname not in dct:
        dct[varname] = value


def any_autor(nazwisko='Kowalski', imiona='Jan Maria', tytul='dr', **kw):
    tytul = Tytul.objects.get_or_create(skrot=tytul)[0]
    return Autor.objects.create(
        nazwisko=nazwisko, tytul=tytul, imiona=imiona, **kw)


def any_uczelnia(nazwa="Uczelnia", skrot="UCL"):
    return Uczelnia.objects.create(nazwa=nazwa, skrot=skrot)

                     
wydzial_cnt = 0                     

def any_wydzial(nazwa=None, skrot=None, uczelnia_skrot="UCL", **kw):
    global wydzial_cnt
    try:
        uczelnia = Uczelnia.objects.get(skrot=uczelnia_skrot)
    except Uczelnia.DoesNotExist:
        uczelnia = any_uczelnia()

    if nazwa is None:
        nazwa = 'Wydział %s' % wydzial_cnt

    if skrot is None:
        skrot = "W%s" % wydzial_cnt
        
    wydzial_cnt += 1

    set_default('uczelnia', uczelnia, kw)
    return Wydzial.objects.create(nazwa=nazwa, skrot=skrot, **kw)


def any_jednostka(nazwa=None, skrot=None, wydzial_skrot="WDZ", **kw):
    """
    :rtype: bpp.models.Jednostka
    """
    if nazwa is None:
        nazwa = 'Jednostka %s' % random.randint(0, 500000)

    if skrot is None:
        skrot = 'J. %s' % random.randint(0, 5000000)

    try:
        uczelnia = kw.pop('uczelnia')
    except KeyError:
        uczelnia = Uczelnia.objects.all().first()
        if uczelnia is None:
            uczelnia = mommy.make(Uczelnia)

    try:
        wydzial = kw.pop('wydzial')
    except KeyError:
        try:
            wydzial = Wydzial.objects.get(skrot=wydzial_skrot)
        except Wydzial.DoesNotExist:
            wydzial = mommy.make(Wydzial, uczelnia=uczelnia)

    return mommy.make(Jednostka, nazwa=nazwa, skrot=skrot, wydzial=wydzial, uczelnia=uczelnia, **kw)


CURRENT_YEAR = datetime.now().year


def any_wydawnictwo(klass, rok=None, **kw):
    if rok is None:
        rok = CURRENT_YEAR

    c = time.time()
    kl = str(klass).split('.')[-1].replace("'>", "")

    kw_wyd = dict(
        tytul="Tytul %s %s" % (kl, c),
        tytul_oryginalny="Tytul oryginalny %s %s" % (kl, c),
        uwagi="Uwagi %s %s" % (kl, c),
        szczegoly='Szczegóły %s %s' % (kl, c))

    if klass == Patent:
        del kw_wyd['tytul']

    for key, value in list(kw_wyd.items()):
        set_default(key, value, kw)

    Status_Korekty.objects.get_or_create(pk=1, nazwa='przed korektą')

    return mommy.make(klass, rok=rok, **kw)


def any_ciagle(**kw):
    """
    :rtype: bpp.models.Wydawnictwo_Ciagle
    """
    if 'zrodlo' not in kw:
        set_default('zrodlo', any_zrodlo(), kw)
    set_default('informacje', 'zrodlo-informacje', kw)
    set_default('issn', '123-IS-SN-34', kw)
    return any_wydawnictwo(Wydawnictwo_Ciagle, **kw)


def any_zwarte_base(klass, **kw):
    if klass not in [Praca_Doktorska, Praca_Habilitacyjna, Patent]:
        set_default('liczba_znakow_wydawniczych', 31337, kw)

    set_default('informacje', 'zrodlo-informacje dla zwarte', kw)

    if klass not in [Patent]:
        set_default('miejsce_i_rok', 'Lublin %s' % CURRENT_YEAR, kw)
        set_default('wydawnictwo', 'Wydawnictwo FOLIUM', kw)
        set_default('isbn', '123-IS-BN-34', kw)
        set_default('redakcja', 'Redakcja', kw)

    return any_wydawnictwo(klass, **kw)


def any_zwarte(**kw):
    """
    :rtype: bpp.models.Wydawnictwo_Zwarte
    """
    return any_zwarte_base(Wydawnictwo_Zwarte, **kw)


def any_habilitacja(**kw):
    """
    :rtype: bpp.models.Praca_Habilitacyjna
    """
    if 'jednostka' not in kw:
        kw['jednostka'] = any_jednostka()
    return any_zwarte_base(Praca_Habilitacyjna, **kw)


def any_doktorat(**kw):
    """
    :rtype: bpp.models.Praca_Habilitacyjna
    """
    if 'jednostka' not in kw:
        kw['jednostka'] = any_jednostka()
    return any_zwarte_base(Praca_Doktorska, **kw)

def any_patent(**kw):
    """
    :rtype: bpp.models.Patent
    """
    return any_zwarte_base(Patent, **kw)


def any_zrodlo(**kw):
    """
    :rtype: bpp.models.Zrodlo
    """
    if 'nazwa' not in kw:
        kw['nazwa'] = "Zrodlo %s" % time.time()

    if 'skrot' not in kw:
        kw['skrot'] = "Zrod. %s" % time.time()

    return mommy.make(Zrodlo, **kw)


def _lookup_fun(klass):
    def fun(skrot):
        return klass.objects.filter(skrot=skrot)
    return fun


typ_kbn = _lookup_fun(Typ_KBN)
jezyk = _lookup_fun(Jezyk)
charakter = _lookup_fun(Charakter_Formalny)

def scroll_into_view(browser, arg):
    return browser.execute_script("document.getElementById('" + arg + "').scrollIntoView(); window.scrollBy(0,-100);")


def show_element(browser, element):
    browser.driver.execute_script("arguments[0].scrollIntoView();", element._element)


def select_select2_autocomplete(browser, element_id, value, delay_before_enter=0.1, delay_after_selection=0.2):
    element = browser.find_by_id(element_id)[0]
    sibling = element.find_by_xpath("following-sibling::span")
    scroll_into_view(browser, element_id)
    sibling.click()
    time.sleep(0.1)
    active = element.parent.switch_to.active_element
    active.send_keys(value)
    time.sleep(delay_before_enter)
    element.parent.switch_to.active_element.send_keys(Keys.ENTER)
    time.sleep(delay_after_selection)

def select_select2_clear_selection(browser, element_id):
    element = browser.find_by_id(element_id)[0]
    browser.execute_script(
        "$('#" + element_id + "').val(null).trigger('change')")
    time.sleep(0.2)
