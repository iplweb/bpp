"""
Tests for admin form field population, auto-completion, and form behavior.

This module contains Selenium tests that verify:
- Automatic population of form fields (strona, tom, nr_zeszytu)
- Character/sheet count calculations
- Points auto-fill functionality
- Author form field completion and clearing
- Custom author name entries
"""

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.expected_conditions import alert_is_present

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.db import transaction
from selenium.webdriver.support.wait import WebDriverWait

from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import (
    add_extra_autor_inline,
    any_autor,
    any_ciagle,
    any_jednostka,
    assertPopupContains,
    proper_click_by_id,
    proper_click_element,
)
from bpp.tests.util import (
    CURRENT_YEAR,
    any_zrodlo,
    select_select2_autocomplete,
    select_select2_clear_selection,
    show_element,
)
from django_bpp.selenium_util import (
    LONG_WAIT_TIME,
    SHORT_WAIT_TIME,
    wait_for,
    wait_for_page_load,
)

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def trigger_event(elem, event):
    """Trigger a jQuery event on an element."""
    elem.parent.driver.execute_script(
        "return django.jQuery(arguments[0]).trigger(arguments[1]).get();",
        "#" + elem["id"],
        event,
    )


@pytest.fixture
def autorform_jednostka(db):
    """Create an author with a unit for autorform tests."""
    with transaction.atomic():
        a = any_autor(nazwisko="KOWALSKI", imiona="Jan Sebastian")
        j = any_jednostka(nazwa="WTF LOL")
        j.dodaj_autora(a)
    return j


@pytest.fixture
def autorform_browser(admin_browser, db, channels_live_server):
    """Set up browser for autorform tests."""
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(channels_live_server.url + url)

    admin_browser.execute_script("window.onbeforeunload = function(e) {};")
    return admin_browser


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_uzupelnij_strona_tom_nr_zeszytu(url, admin_browser, channels_live_server):
    """Test automatic population of page, volume, and issue number fields."""
    url = reverse(f"admin:bpp_{url}_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(channels_live_server.url + url)

    WebDriverWait(admin_browser, SHORT_WAIT_TIME).until(
        lambda browser: not admin_browser.find_by_name("informacje").is_empty()
    )
    try:
        WebDriverWait(admin_browser, LONG_WAIT_TIME).until(
            lambda browser: not admin_browser.find_by_id("id_strony_get").is_empty()
        )
    except TimeoutException as e:
        raise e

    admin_browser.find_by_name("informacje").type("1993 vol. 5 z. 1")
    admin_browser.find_by_name("szczegoly").type("s. 4-3")

    elem = admin_browser.find_by_id("id_strony_get")
    show_element(admin_browser, elem)
    elem.click()

    WebDriverWait(admin_browser, SHORT_WAIT_TIME).until(
        lambda browser: browser.find_by_name("tom").value != ""
    )

    assert admin_browser.find_by_name("strony").value == "4-3"
    assert admin_browser.find_by_name("tom").value == "5"

    if url == "wydawnictwo_ciagle":
        assert admin_browser.find_by_name("nr_zeszytu").value == "1"


def test_liczba_znakow_wydawniczych_liczba_arkuszy_wydawniczych(
    admin_browser, channels_live_server
):
    """Test automatic calculation between character count and sheet count."""
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(channels_live_server.url + url)

    try:
        WebDriverWait(admin_browser, SHORT_WAIT_TIME).until(
            lambda browser: not admin_browser.find_by_id(
                "id_liczba_arkuszy_wydawniczych"
            ).is_empty()
        )
    except TimeoutException as e:
        raise e

    admin_browser.execute_script(
        "django.jQuery('#id_liczba_znakow_wydawniczych').val('40000').change()"
    )
    assert admin_browser.find_by_id("id_liczba_arkuszy_wydawniczych").value == "1.00"

    admin_browser.execute_script(
        "django.jQuery('#id_liczba_arkuszy_wydawniczych').val('0.5').change()"
    )
    assert admin_browser.find_by_id("id_liczba_znakow_wydawniczych").value == "20000"


@pytest.mark.django_db(transaction=True)
def test_automatycznie_uzupelnij_punkty(admin_browser, channels_live_server):
    """Test automatic points population button without selecting source first."""
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")

    with wait_for_page_load(admin_browser):
        admin_browser.visit(channels_live_server.url + url)

    any_zrodlo(nazwa="FOO BAR")

    wait_for(lambda: len(admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")))

    elem = admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    show_element(admin_browser, elem)
    elem.click()
    assertPopupContains(admin_browser, "Najpierw wybierz jakie")

    select_select2_autocomplete(admin_browser, "id_zrodlo", "FOO")

    proper_click_by_id(admin_browser, "id_wypelnij_pola_punktacji_button")
    assertPopupContains(admin_browser, "Uzupełnij pole")

    admin_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_admin_uzupelnij_punkty(admin_browser, channels_live_server, denorms):
    """Test automatic points population from source scoring data."""
    z = any_zrodlo(nazwa="WTF LOL")

    kw = dict(zrodlo=z)
    f = Punktacja_Zrodla.objects.create
    f(impact_factor=10.1, punkty_kbn=10.2, rok=CURRENT_YEAR, **kw)
    f(impact_factor=11.1, punkty_kbn=11.2, rok=CURRENT_YEAR + 1, **kw)

    c = any_ciagle(zrodlo=z, impact_factor=5, punkty_kbn=5)

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    with wait_for_page_load(admin_browser):
        admin_browser.visit(channels_live_server.url + url)

    rok = admin_browser.find_by_id("id_rok")
    punkty_kbn = admin_browser.find_by_id("id_punkty_kbn")

    assert rok.value == str(CURRENT_YEAR)
    assert punkty_kbn.value == "5.00"

    button = admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")

    proper_click_element(admin_browser, button)

    wait_for(lambda: button.value == "Wypełniona!")
    wait_for(lambda: punkty_kbn.value == "10.20")

    trigger_event(rok, "change")
    # Po zmianie roku LUB źródła przycisk ma się zmienić
    wait_for(lambda: button.value == "Wypełnij pola punktacji")

    # Zwiększymy rok o 1 i sprawdzimy, czy zmieni się punktacja
    admin_browser.fill("rok", str(CURRENT_YEAR + 1))

    button = admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    proper_click_element(admin_browser, button)
    wait_for(lambda: punkty_kbn.value == "11.20")

    # Teraz usuniemy źródło i sprawdzimy, czy przycisk zmieni nazwę
    assert button.value == "Wypełniona!"

    select_select2_clear_selection(admin_browser, "id_zrodlo")
    WebDriverWait(admin_browser.driver, SHORT_WAIT_TIME).until(
        lambda browser: admin_browser.find_by_id(
            "id_wypelnij_pola_punktacji_button"
        ).value
        == "Wypełnij pola punktacji"
    )

    admin_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_upload_punkty(admin_browser, channels_live_server):
    """Test uploading points to source scoring data."""
    any_zrodlo(nazwa="WTF LOL")

    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    admin_browser.visit(channels_live_server.url + url)

    select_select2_autocomplete(admin_browser, "id_zrodlo", "WTF")

    rok = admin_browser.find_by_id("id_rok")
    show_element(admin_browser, rok)
    admin_browser.fill("rok", str(CURRENT_YEAR))

    show_element(admin_browser, admin_browser.find_by_id("id_impact_factor"))
    admin_browser.fill("impact_factor", "1")

    elem = admin_browser.find_by_id("id_dodaj_punktacje_do_zrodla_button")
    show_element(admin_browser, elem)
    elem.click()

    WebDriverWait(admin_browser.driver, SHORT_WAIT_TIME).until(
        lambda browser: Punktacja_Zrodla.objects.count() == 1
    )
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 1

    admin_browser.fill("impact_factor", "2")
    proper_click_by_id(admin_browser, "id_dodaj_punktacje_do_zrodla_button")

    WebDriverWait(admin_browser.driver, SHORT_WAIT_TIME).until(alert_is_present())
    assertPopupContains(admin_browser, "Punktacja dla tego roku już istnieje")
    WebDriverWait(admin_browser.driver, SHORT_WAIT_TIME).until(
        lambda browser: not alert_is_present()(browser)
    )

    WebDriverWait(admin_browser.driver, SHORT_WAIT_TIME).until(
        lambda browser: Punktacja_Zrodla.objects.all()[0].impact_factor == 2
    )

    admin_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_autorform_uzupelnianie_jednostki(autorform_browser, autorform_jednostka):
    """Test automatic unit population when selecting an author."""
    add_extra_autor_inline(autorform_browser)

    select_select2_autocomplete(autorform_browser, "id_autorzy_set-0-autor", "KOWALSKI")

    autorform_browser.find_by_id("id_autorzy_set-0-jednostka")
    WebDriverWait(autorform_browser, SHORT_WAIT_TIME).until(
        lambda browser: autorform_browser.find_by_id("id_autorzy_set-0-jednostka").value
        == str(autorform_jednostka.pk)
    )


def test_autorform_kasowanie_autora(autorform_browser, autorform_jednostka):
    """Test that clearing author also clears unit selection."""
    # kliknij "dodaj powiazanie autor-wydawnictwo"
    add_extra_autor_inline(autorform_browser)

    # uzupełnij autora
    select_select2_autocomplete(autorform_browser, "id_autorzy_set-0-autor", "KOW")

    def jednostka_ustawiona():
        jed = autorform_browser.find_by_id("id_autorzy_set-0-jednostka")
        if jed.value != "":
            return jed.value

    wait_for(jednostka_ustawiona)

    # Jednostka ustawiona. Usuń autora:
    select_select2_clear_selection(autorform_browser, "id_autorzy_set-0-autor")

    # jednostka nie jest wybrana
    try:
        WebDriverWait(autorform_browser.driver, SHORT_WAIT_TIME).until(
            lambda browser: autorform_browser.find_by_id(
                "id_autorzy_set-0-jednostka"
            ).value.find("\n")
            != -1
        )
    except TimeoutException as e:
        raise e
    #  assert jed.value.find("\n") != -1

    autorform_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_admin_wydawnictwo_ciagle_dowolnie_zapisane_nazwisko(
    admin_browser, channels_live_server, autor_jan_kowalski
):
    """Test entering a custom author name in the zapisany_jako field."""
    browser = admin_browser

    with wait_for_page_load(browser):
        browser.visit(
            channels_live_server.url + reverse("admin:bpp_wydawnictwo_ciagle_add")
        )

    xp1 = "/html/body/div[2]/article/div/form/div/div[1]/ul/li/a"
    wait_for(lambda: len(browser.find_by_xpath(xp1)) > 0)
    elem = browser.find_by_xpath(xp1)
    proper_click_element(browser, elem[0])

    element = browser.find_by_xpath(
        "/html/body/div[2]/article/div/form/div/div[1]/div[2]/div/a"
    )
    proper_click_element(browser, element)
    # scroll_into_view()
    wait_for(
        lambda: browser.find_by_id("id_autorzy_set-0-autor"),
        max_seconds=SHORT_WAIT_TIME,
    )

    select_select2_autocomplete(browser, "id_autorzy_set-0-autor", "Kowalski Jan")

    select_select2_autocomplete(
        browser, "id_autorzy_set-0-zapisany_jako", "Dowolny tekst"
    )

    if browser.find_by_id("id_autorzy_set-0-zapisany_jako").value != "Dowolny tekst":
        print("1")  # for debugging

    assert browser.find_by_id("id_autorzy_set-0-zapisany_jako").value == "Dowolny tekst"
