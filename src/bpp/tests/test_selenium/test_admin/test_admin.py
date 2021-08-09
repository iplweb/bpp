# -*- encoding: utf-8 -*-
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.expected_conditions import alert_is_present

from bpp.models.const import CHARAKTER_OGOLNY_KSIAZKA, TO_AUTOR

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.db import transaction
from model_mommy import mommy
from selenium.webdriver.support.wait import WebDriverWait

from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Ciagle,
)
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
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

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_uzupelnij_strona_tom_nr_zeszytu(url, admin_browser, asgi_live_server):
    url = reverse("admin:bpp_%s_add" % url)
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

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
    admin_browser, asgi_live_server
):
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

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
def test_automatycznie_uzupelnij_punkty(admin_browser, asgi_live_server):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")

    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

    any_zrodlo(nazwa="FOO BAR")

    elem = admin_browser.find_by_id("id_wypelnij_pola_punktacji_button")
    show_element(admin_browser, elem)
    elem.click()
    assertPopupContains(admin_browser, "Najpierw wybierz jakie")

    select_select2_autocomplete(admin_browser, "id_zrodlo", "FOO")

    proper_click_by_id(admin_browser, "id_wypelnij_pola_punktacji_button")
    assertPopupContains(admin_browser, "Uzupełnij pole")

    admin_browser.execute_script("window.onbeforeunload = function(e) {};")


def trigger_event(elem, event):
    # import pytest; pytest.set_trace()e
    elem.parent.driver.execute_script(
        "return django.jQuery(arguments[0]).trigger(arguments[1]).get();",
        "#" + elem["id"],
        event,
    )


def test_admin_uzupelnij_punkty(admin_browser, asgi_live_server):
    z = any_zrodlo(nazwa="WTF LOL")

    kw = dict(zrodlo=z)
    f = Punktacja_Zrodla.objects.create
    f(impact_factor=10.1, punkty_kbn=10.2, rok=CURRENT_YEAR, **kw)
    f(impact_factor=11.1, punkty_kbn=11.2, rok=CURRENT_YEAR + 1, **kw)

    c = any_ciagle(zrodlo=z, impact_factor=5, punkty_kbn=5)

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

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


def test_upload_punkty(admin_browser, asgi_live_server):
    any_zrodlo(nazwa="WTF LOL")

    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    admin_browser.visit(asgi_live_server.url + url)

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


@pytest.fixture
def autorform_jednostka(db):
    with transaction.atomic():
        a = any_autor(nazwisko="KOWALSKI", imiona="Jan Sebastian")
        j = any_jednostka(nazwa="WTF LOL")
        j.dodaj_autora(a)
    return j


@pytest.fixture
def autorform_browser(admin_browser, db, asgi_live_server):
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

    admin_browser.execute_script("window.onbeforeunload = function(e) {};")
    return admin_browser


def test_autorform_uzupelnianie_jednostki(autorform_browser, autorform_jednostka):
    add_extra_autor_inline(autorform_browser)

    select_select2_autocomplete(autorform_browser, "id_autorzy_set-0-autor", "KOWALSKI")

    autorform_browser.find_by_id("id_autorzy_set-0-jednostka")
    WebDriverWait(autorform_browser, SHORT_WAIT_TIME).until(
        lambda browser: autorform_browser.find_by_id("id_autorzy_set-0-jednostka").value
        == str(autorform_jednostka.pk)
    )


def find_autocomplete_widget(browser, id):
    for elem in browser.find_by_css(".yourlabs-autocomplete"):
        try:
            dii = elem["data-input-id"]
        except KeyError:
            continue

        if dii == id:
            return elem


def test_autorform_kasowanie_autora(autorform_browser, autorform_jednostka):
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


def test_bug_on_user_add(admin_browser, asgi_live_server):
    admin_browser.visit(asgi_live_server.url + reverse("admin:bpp_bppuser_add"))
    admin_browser.fill("username", "as")
    admin_browser.fill("password1", "as")
    admin_browser.fill("password2", "as")
    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_continue").click()

    admin_browser.wait_for_condition(lambda browser: "Zmień użytkownik" in browser.html)


def test_admin_wydawnictwo_zwarte_uzupelnij_rok(
    wydawnictwo_zwarte, admin_browser, asgi_live_server, transactional_db
):
    """
    :type admin_browser: splinter.driver.webdriver.remote.WebDriver
    """

    browser = admin_browser

    browser.visit(asgi_live_server.url + reverse("admin:bpp_wydawnictwo_zwarte_add"))

    rok = browser.find_by_id("id_rok")
    button = browser.find_by_id("id_rok_button")

    assert rok.value == ""

    browser.fill("miejsce_i_rok", "Lublin 2002")

    proper_click_element(browser, button)

    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    chf = Charakter_Formalny.objects.create(
        nazwa="charakter", skrot="ch", charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA
    )

    wydawnictwo_zwarte.rok = 1997
    wydawnictwo_zwarte.charakter_formalny = chf
    wydawnictwo_zwarte.save()

    select_select2_autocomplete(
        browser, "id_wydawnictwo_nadrzedne", "Wydawnictwo Zwarte"
    )

    browser.fill("rok", "")
    proper_click_element(browser, button)
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    browser.fill("miejsce_i_rok", "")
    proper_click_element(browser, button)
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "1997"
    )


def test_admin_wydawnictwo_ciagle_uzupelnij_rok(admin_browser, asgi_live_server):
    """
    :type admin_browser: splinter.driver.webdriver.remote.WebDriver
    """

    browser = admin_browser

    with wait_for_page_load(browser):
        browser.visit(
            asgi_live_server.url + reverse("admin:bpp_wydawnictwo_ciagle_add")
        )
    browser.fill("informacje", "Lublin 2002 test")
    elem = browser.find_by_id("id_rok_button")
    proper_click_element(browser, elem)

    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    browser.fill("informacje", "")
    proper_click_by_id(browser, "id_rok_button")
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok_button").value == "Brak danych"
    )


def test_admin_wydawnictwo_ciagle_dowolnie_zapisane_nazwisko(
    admin_browser, asgi_live_server, autor_jan_kowalski
):
    """
    :type admin_browser: splinter.driver.webdriver.remote.WebDriver
    """

    browser = admin_browser

    with wait_for_page_load(browser):
        browser.visit(
            asgi_live_server.url + reverse("admin:bpp_wydawnictwo_ciagle_add")
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


@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(
    "url",
    ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"],
)
def test_admin_domyslnie_afiliuje_nowy_rekord(
    admin_browser,
    asgi_live_server,
    url,
    expected,
):
    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    mommy.make(Uczelnia, domyslnie_afiliuje=expected)

    browser = admin_browser
    with wait_for_page_load(browser):
        browser.visit(asgi_live_server.url + reverse(f"admin:bpp_{url}_add"))

    add_extra_autor_inline(browser)

    v = browser.find_by_id("id_autorzy_set-0-afiliuje")
    assert v.checked == expected


@pytest.mark.parametrize("afiliowany", [True, False])
@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(
    "url,klasa",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
        ("patent", Patent),
    ],
)
@pytest.mark.django_db(transaction=True)
def test_admin_domyslnie_afiliuje_istniejacy_rekord(
    admin_browser, asgi_live_server, url, klasa, expected, afiliowany
):
    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    mommy.make(Uczelnia, domyslnie_afiliuje=expected)
    autor = mommy.make(Autor, nazwisko="Kowal", imiona="Ski")
    jednostka = mommy.make(Jednostka, nazwa="Lol", skrot="WT")
    wydawnictwo = mommy.make(klasa, tytul_oryginalny="test")
    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=TO_AUTOR
    )
    wa = wydawnictwo.dodaj_autora(autor, jednostka, zapisany_jako="Wutlolski")
    wa.afiliowany = afiliowany
    wa.save()

    browser = admin_browser
    with wait_for_page_load(browser):
        browser.visit(
            asgi_live_server.url
            + reverse(f"admin:bpp_{url}_change", args=(wydawnictwo.pk,))
        )

    add_extra_autor_inline(browser)

    v = browser.find_by_id("id_autorzy_set-1-afiliuje")
    assert v.checked == expected
