# -*- encoding: utf-8 -*-

"""Ten moduł zawiera 'normalne', dla ludzi funkcje, które mogą być używane
do ustawiania testów."""
import random
import re
import time
import warnings
from datetime import datetime

from django.urls import reverse
from model_mommy import mommy
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.expected_conditions import visibility_of
from selenium.webdriver.support.wait import WebDriverWait
from splinter.exceptions import ElementDoesNotExist

from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jednostka,
    Jezyk,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Typ_KBN,
    Tytul,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
    Zrodlo,
)
from bpp.models.system import Status_Korekty

from django_bpp.selenium_util import (
    LONG_WAIT_TIME,
    SHORT_WAIT_TIME,
    wait_for,
    wait_for_page_load,
)


def setup_mommy():
    mommy.generators.add(
        "django.contrib.postgres.fields.array.ArrayField", lambda x: []
    )

    mommy.generators.add(
        "django.contrib.postgres.search.SearchVectorField", lambda x=None: None
    )


def set_default(varname, value, dct):
    if varname not in dct:
        dct[varname] = value


def any_autor(nazwisko="Kowalski", imiona="Jan Maria", tytul="dr", **kw):
    tytul = Tytul.objects.get_or_create(skrot=tytul)[0]
    return Autor.objects.create(nazwisko=nazwisko, tytul=tytul, imiona=imiona, **kw)


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
        nazwa = "Wydział %s" % wydzial_cnt

    if skrot is None:
        skrot = "W%s" % wydzial_cnt

    wydzial_cnt += 1

    set_default("uczelnia", uczelnia, kw)
    return Wydzial.objects.create(nazwa=nazwa, skrot=skrot, **kw)


def any_jednostka(nazwa=None, skrot=None, wydzial_skrot="WDZ", **kw):
    """
    :rtype: bpp.models.Jednostka
    """
    if nazwa is None:
        nazwa = "Jednostka %s" % random.randint(0, 500000)

    if skrot is None:
        skrot = "J. %s" % random.randint(0, 5000000)

    try:
        uczelnia = kw.pop("uczelnia")
    except KeyError:
        uczelnia = Uczelnia.objects.all().first()
        if uczelnia is None:
            uczelnia = mommy.make(Uczelnia)

    try:
        wydzial = kw.pop("wydzial")
    except KeyError:
        try:
            wydzial = Wydzial.objects.get(skrot=wydzial_skrot)
        except Wydzial.DoesNotExist:
            wydzial = mommy.make(Wydzial, uczelnia=uczelnia)

    ret = Jednostka.objects.create(
        nazwa=nazwa, skrot=skrot, wydzial=wydzial, uczelnia=uczelnia, **kw
    )
    ret.refresh_from_db()
    return ret


CURRENT_YEAR = datetime.now().year


def any_wydawnictwo(klass, rok=None, **kw):
    if rok is None:
        rok = CURRENT_YEAR

    c = time.time()
    kl = str(klass).split(".")[-1].replace("'>", "")

    kw_wyd = dict(
        tytul="Tytul %s %s" % (kl, c),
        tytul_oryginalny="Tytul oryginalny %s %s" % (kl, c),
        uwagi="Uwagi %s %s" % (kl, c),
        szczegoly="Szczegóły %s %s" % (kl, c),
    )

    if klass == Patent:
        del kw_wyd["tytul"]

    for key, value in list(kw_wyd.items()):
        set_default(key, value, kw)

    Status_Korekty.objects.get_or_create(pk=1, nazwa="przed korektą")

    return mommy.make(klass, rok=rok, **kw)


def any_ciagle(**kw):
    """
    :rtype: bpp.models.Wydawnictwo_Ciagle
    """
    if "zrodlo" not in kw:
        set_default("zrodlo", any_zrodlo(), kw)
    set_default("informacje", "zrodlo-informacje", kw)
    set_default("issn", "123-IS-SN-34", kw)
    return any_wydawnictwo(Wydawnictwo_Ciagle, **kw)


def any_zwarte_base(klass, **kw):
    if klass not in [Praca_Doktorska, Praca_Habilitacyjna, Patent]:
        set_default("liczba_znakow_wydawniczych", 31337, kw)

    set_default("informacje", "zrodlo-informacje dla zwarte", kw)

    if klass not in [Patent]:
        set_default("miejsce_i_rok", "Lublin %s" % CURRENT_YEAR, kw)
        set_default("wydawca_opis", "Wydawnictwo FOLIUM", kw)
        set_default("isbn", "123-IS-BN-34", kw)
        set_default("redakcja", "Redakcja", kw)

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
    if "jednostka" not in kw:
        kw["jednostka"] = any_jednostka()
    return any_zwarte_base(Praca_Habilitacyjna, **kw)


def any_doktorat(**kw):
    """
    :rtype: bpp.models.Praca_Habilitacyjna
    """
    if "jednostka" not in kw:
        kw["jednostka"] = any_jednostka()
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
    if "nazwa" not in kw:
        kw["nazwa"] = "Zrodlo %s" % time.time()

    if "skrot" not in kw:
        kw["skrot"] = "Zrod. %s" % time.time()

    return mommy.make(Zrodlo, **kw)


def _lookup_fun(klass):
    def fun(skrot):
        return klass.objects.filter(skrot=skrot)

    return fun


typ_kbn = _lookup_fun(Typ_KBN)
jezyk = _lookup_fun(Jezyk)
charakter = _lookup_fun(Charakter_Formalny)


def scroll_into_view(browser, arg):
    warnings.warn("Uzyj show_element zamiast", DeprecationWarning, stacklevel=2)
    s = f"document.getElementById('{arg}').scrollIntoView(); window.scrollBy(0,-100);"
    return browser.execute_script(s)


def show_element(browser, element):
    s = """
        // console.log('enter---');
        window.scrollTo(0, 0);
        var viewPortHeight = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);
        // console.log(viewPortHeight);
        var elementTop = arguments[0].getBoundingClientRect().top;
        // console.log(elementTop);
        if (elementTop < (viewPortHeight/2)*0.5 || elementTop > (viewPortHeight/2)*1.5 ) {
            // console.log("scrolling");
            window.scrollTo(0, Math.max(0, elementTop-(viewPortHeight/2)));
            // console.log(Math.max(0, elementTop-(viewPortHeight/2)));
        }
        """
    return browser.execute_script(s, element._element)


def select_select2_autocomplete(
    browser, element_id, value, wait_for_new_value=True, value_before_enter=None
):
    """
    Wypełnia kontrolkę Select2

    :param browser: splinter.Browser
    :param element_id: ID elementu (tekst)
    :param value: tekst do wpisania
    """
    # Znajdź interesujący nas select2-autocomplete
    element = browser.find_by_id(element_id)[0]
    sibling = element.find_by_xpath("following-sibling::span")

    if len(sibling) == 0:
        raise ElementDoesNotExist("sibling not found")

    sibling = sibling.first

    # Umieść go na widoku
    show_element(browser, sibling)

    # Kliknij w aktywny element, następnie wyślij klawisze do aktywnego
    # elementu, który się pojawił (wyskakujący pop-up select2)
    # następnie wyślij ENTER, następnie sprawdź, czy ustawiona została
    # nowa wartość. Jeżeli nie, to powtórz, maksimum 3 razy:

    # tries = 0
    # while True:

    old_active = element.parent.switch_to.active_element
    while True:
        sibling.click()
        time.sleep(random.randint(100, 1000) / 1000)
        new_active = element.parent.switch_to.active_element

        if new_active != old_active:
            break

    old_value = None

    while old_value is None:
        old_value = browser.find_by_id(f"select2-{element_id}-container").text
        time.sleep(0.3)

    # for letter in value:
    new_active.send_keys(value)
    time.sleep(1)

    wait_for(
        lambda: "Trwa wyszukiwanie…"
        not in browser.find_by_id(f"select2-{element_id}-results").value
    )

    if value_before_enter:
        try:
            wait_for(
                lambda: value_before_enter
                in browser.find_by_id(f"select2-{element_id}-results").value,
                max_seconds=LONG_WAIT_TIME,
            )
        except TimeoutError as e:
            raise e
    new_active.send_keys(Keys.ENTER)
    time.sleep(0.5)

    if wait_for_new_value:
        try:
            wait_for(
                lambda: browser.find_by_id(f"select2-{element_id}-container").text
                != old_value
            )
        except TimeoutError as e:
            raise e


def select_select2_clear_selection(browser, element_id):
    browser.find_by_id(element_id)[0]
    browser.execute_script(
        "django.jQuery('#" + element_id + "').val(null).trigger('change')"
    )


def select_element_by_text(browser, element_id, text):
    element = browser.find_by_id(element_id)
    show_element(browser, element)
    element.select_by_text(text)


def set_element(browser, element_id, text):
    element = browser.find_by_id(element_id)
    show_element(browser, element)
    element.type(text)


def submit_admin_form(browser):
    with wait_for_page_load(browser):
        browser.execute_script(
            'django.jQuery("input[type=submit].grp-default").click()'
        )


def proper_click_element(browser, element):
    # show_element(browser, element)
    # return element.click()
    browser.execute_script("arguments[0].scrollIntoView();", element._element)
    WebDriverWait(browser, SHORT_WAIT_TIME).until(visibility_of(element._element))
    browser.execute_script("arguments[0].click();", element._element)


def proper_click_by_id(browser, arg):
    elem = browser.find_by_id(arg)
    proper_click_element(browser, elem)


def assertPopupContains(browser, text, accept=True):
    """Switch to popup, assert it contains at least a part
    of the text, close the popup. Error otherwise.
    """
    alert = browser.driver.switch_to.alert
    if text not in alert.text:
        raise AssertionError("%r not found in %r" % (text, alert.text))
    if accept:
        alert.accept()


def add_extra_autor_inline(browser, no_current_inlines=0):
    elem = None

    WebDriverWait(browser, SHORT_WAIT_TIME).until(
        lambda browser: not browser.find_by_css(".grp-add-handler").is_empty()
    )

    elems = browser.find_by_css(".grp-add-handler")

    for e in elems:
        if (
            e.visible
            and e.text.find("Dodaj") >= 0
            and e.text.find("powiązanie autora") >= 0
        ):
            elem = e
            break

    proper_click_element(browser, elem)

    try:
        wait_for(
            lambda: not browser.find_by_id(
                f"id_autorzy_set-{no_current_inlines}-autor"
            ).is_empty(),
            max_seconds=LONG_WAIT_TIME,
        )
    except TimeoutError as e:
        raise e


def randomobj(model):
    return model.objects.order_by("?").first()


def quick_find_by_id(browser, id):
    if f'id="{id}"' in browser.html:
        return browser.find_by_id(id, wait_time=0.01)


def fill_admin_form(
    browser,
    zrodlo=None,
    tytul_oryginalny="tytul oryginalny",
    jezyk=None,
    charakter_formalny=None,
    typ_kbn=None,
    status_korekty=None,
    rok=None,
):
    set_element(browser, "id_tytul_oryginalny", tytul_oryginalny)

    if quick_find_by_id(browser, "id_zrodlo"):
        if zrodlo is None:
            # from bpp.models import Zrodlo
            zrodlo = randomobj(Zrodlo)
        select_select2_autocomplete(browser, "id_zrodlo", zrodlo.nazwa)

    if quick_find_by_id(browser, "id_jezyk"):
        if jezyk is None:
            # from bpp.models import Jezk
            jezyk = randomobj(Jezyk)
        select_element_by_text(browser, "id_jezyk", jezyk.nazwa)

    if quick_find_by_id(browser, "id_charakter_formalny"):
        if charakter_formalny is None:
            # charakter_formalny = randomobj(Charakter_Formalny)
            charakter_formalny = Charakter_Formalny.objects.get(nazwa="Broszura")
        select_element_by_text(
            browser, "id_charakter_formalny", " " + charakter_formalny.nazwa
        )

    if quick_find_by_id(browser, "id_typ_kbn"):
        if typ_kbn is None:
            typ_kbn = randomobj(Typ_KBN)
        select_element_by_text(browser, "id_typ_kbn", typ_kbn.nazwa)

    if status_korekty is None:
        status_korekty = randomobj(Status_Korekty)
    select_element_by_text(browser, "id_status_korekty", "przed korektą")

    if rok is None:
        rok = random.randint(1, 2100)
    set_element(browser, "id_rok", rok)


def fill_admin_inline(
    browser,
    autor,
    jednostka,
    zapisany_jako=None,
    procent=None,
    no=0,
    prefix=None,
    dyscyplina=None,
):
    "Daj prefix równy 'id_' aby wypełniać pojedyncze formularze (nie inlines)"

    # Poza tymi wypełnianymi poniżej sa jeszcze:
    # autorzy_set-0-typ_odpowiedzialnosci
    # autorzy_set-0-afiliuje
    # autorzy_set-0-zatrudniony
    # autorzy_set-0-kolejnosc
    # autorzy_set-0-rekord
    # autorzy_set-0-id

    if prefix is None:
        prefix = f"id_autorzy_set-{no}-"

    select_select2_autocomplete(
        browser, f"{prefix}autor", f"{autor.nazwisko} {autor.imiona}"
    )
    select_select2_autocomplete(browser, f"{prefix}jednostka", jednostka.nazwa)
    if zapisany_jako is None:
        zapisany_jako = f"{autor.nazwisko} {autor.imiona}"
    select_select2_autocomplete(browser, f"{prefix}zapisany_jako", zapisany_jako)
    if procent is not None:
        set_element(browser, f"{prefix}procent", procent)
    if procent == -1:
        set_element(browser, f"{prefix}procent", str(random.randint(1, 100)) + ".00")

    if dyscyplina:
        # set_element(browser, f"{prefix}dyscyplina_naukowa", dyscyplina)
        select_select2_autocomplete(
            browser, f"{prefix}dyscyplina_naukowa", dyscyplina.nazwa
        )


def submitted_form_bad(browser, wait_time=SHORT_WAIT_TIME):
    WebDriverWait(browser.driver, wait_time).until(
        lambda driver: "Prosimy poprawić" in driver.page_source
    )
    return True


def submitted_form_good(browser, wait_time=SHORT_WAIT_TIME):
    WebDriverWait(browser.driver, wait_time).until(
        lambda driver: "został dodany pomyślnie" in driver.page_source
    )
    return True


def browse_praca_url(model):
    return reverse(
        "bpp:browse_praca_by_slug", args=(model.slug,)
    )  # ContentType.objects.get_for_model(model).pk, model.pk)


def normalize_html(s):
    s = s.replace("\r\n", " ").replace("\n", " ")
    return re.sub(r"\s\s+", " ", s)
