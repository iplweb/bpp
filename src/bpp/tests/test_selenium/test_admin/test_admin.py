# -*- encoding: utf-8 -*-
import time

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.db import transaction
from model_mommy import mommy
from selenium.webdriver.support.wait import WebDriverWait

from bpp.models import Wydawnictwo_Ciagle, Uczelnia, Autor, Jednostka, Typ_Odpowiedzialnosci, TO_AUTOR
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import any_ciagle, any_autor, any_jednostka
from bpp.tests.util import any_zrodlo, CURRENT_YEAR, select_select2_autocomplete, select_select2_clear_selection, \
    show_element
from django_bpp.selenium_util import wait_for_page_load, wait_for
from .helpers import *

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"]
)
def test_uzupelnij_strona_tom_nr_zeszytu(url,
                                         preauth_admin_browser,
                                         live_server):
    url = reverse("admin:bpp_%s_add" % url)
    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.visit(live_server + url)

    preauth_admin_browser.find_by_name("informacje").type("1993 vol. 5 z. 1")
    preauth_admin_browser.find_by_name("szczegoly").type("s. 4-3")

    preauth_admin_browser.execute_script("$('#id_strony_get').click()")
    WebDriverWait(preauth_admin_browser, 10).until(
        lambda browser: browser.find_by_name("tom").value != "")

    assert preauth_admin_browser.find_by_name("strony").value == "4-3"
    assert preauth_admin_browser.find_by_name("tom").value == "5"

    if url == "wydawnictwo_ciagle":
        assert preauth_admin_browser.find_by_name("nr_zeszytu").value == "1"


def test_liczba_znakow_wydawniczych_liczba_arkuszy_wydawniczych(
        preauth_admin_browser, live_server):
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.visit(live_server + url)

    preauth_admin_browser.execute_script(
        "$('#id_liczba_znakow_wydawniczych').val('40000').change()")
    assert preauth_admin_browser.find_by_id(
        "id_liczba_arkuszy_wydawniczych").value == "1.00"

    preauth_admin_browser.execute_script(
        "$('#id_liczba_arkuszy_wydawniczych').val('0.5').change()")
    assert preauth_admin_browser.find_by_id(
        "id_liczba_znakow_wydawniczych").value == "20000"


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
        lambda: autorform_browser.find_by_id("id_autorzy_set-0-autor")
    )

    select_select2_autocomplete(
        autorform_browser,
        "id_autorzy_set-0-autor",
        "KOWALSKI"
    )

    sel = autorform_browser.find_by_id("id_autorzy_set-0-jednostka")
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
        lambda: autorform_browser.find_by_id("id_autorzy_set-0-autor")
    )

    # uzupełnij autora
    select_select2_autocomplete(
        autorform_browser,
        "id_autorzy_set-0-autor",
        "KOW")

    start = time.time()
    while True:
        jed = autorform_browser.find_by_id("id_autorzy_set-0-jednostka")
        if jed.value != '':
            break
        time.sleep(0.1)
        if time.time() - start >= 3:
            raise Exception("Timeout")

    # Jednostka ustawiona. Usuń autora:
    select_select2_clear_selection(
        autorform_browser,
        "id_autorzy_set-0-autor")

    # jednostka nie jest wybrana
    jed = autorform_browser.find_by_id("id_autorzy_set-0-jednostka")
    assert jed.value.find("\n") != -1

    autorform_browser.execute_script("window.onbeforeunload = function(e) {};")


def test_bug_on_user_add(preauth_admin_browser, live_server):
    preauth_admin_browser.visit(live_server + reverse('admin:bpp_bppuser_add'))
    preauth_admin_browser.fill("username", "as")
    preauth_admin_browser.fill("password1", "as")
    preauth_admin_browser.fill("password2", "as")
    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_name("_continue").click()

    preauth_admin_browser.wait_for_condition(
        lambda browser: "Zmień użytkownik" in browser.html
    )


def test_admin_wydawnictwo_zwarte_uzupelnij_rok(
        wydawnictwo_zwarte,
        preauth_admin_browser,
        live_server):
    """
    :type preauth_admin_browser: splinter.driver.webdriver.remote.WebDriver
    """

    browser = preauth_admin_browser

    browser.visit(live_server + reverse('admin:bpp_wydawnictwo_zwarte_add'))

    rok = browser.find_by_id("id_rok")
    button = browser.find_by_id("id_rok_button")

    assert rok.value == ""

    browser.fill("miejsce_i_rok", "Lublin 2002")

    proper_click(browser, "id_rok_button")

    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    wydawnictwo_zwarte.rok = 1997
    wydawnictwo_zwarte.save()

    select_select2_autocomplete(
        browser,
        "id_wydawnictwo_nadrzedne",
        "Wydawnictwo Zwarte"
    )

    browser.fill("rok", "")
    button.click()
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    browser.fill("miejsce_i_rok", "")
    button.click()
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "1997"
    )


def test_admin_wydawnictwo_ciagle_uzupelnij_rok(
        preauth_admin_browser,
        live_server):
    """
    :type preauth_admin_browser: splinter.driver.webdriver.remote.WebDriver
    """

    browser = preauth_admin_browser

    browser.visit(live_server + reverse('admin:bpp_wydawnictwo_ciagle_add'))

    browser.fill("informacje", "Lublin 2002 test")
    proper_click(browser, "id_rok_button")

    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    browser.fill("informacje", "")
    proper_click(browser, "id_rok_button")
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok_button").value == "Brak danych"
    )


def test_admin_wydawnictwo_ciagle_dowolnie_zapisane_nazwisko(
        preauth_admin_browser,
        live_server,
        autor_jan_kowalski):
    """
    :type preauth_admin_browser: splinter.driver.webdriver.remote.WebDriver
    """

    browser = preauth_admin_browser

    browser.visit(live_server + reverse('admin:bpp_wydawnictwo_ciagle_add'))

    elem = browser.find_by_xpath("/html/body/div[2]/article/div/form/div/div[1]/ul/li/a")
    show_element(browser, elem)
    elem.click()

    browser.find_by_xpath("/html/body/div[2]/article/div/form/div/div[1]/div[2]/div/a").click()
    wait_for(
        lambda: browser.find_by_id("id_autorzy_set-0-autor")
    )

    select_select2_autocomplete(
        browser,
        "id_autorzy_set-0-autor",
        "Kowalski Jan"
    )

    select_select2_autocomplete(
        browser,
        "id_autorzy_set-0-zapisany_jako",
        "Dowolny tekst"
    )

    assert browser.find_by_id("id_autorzy_set-0-zapisany_jako").value == "Dowolny tekst"


@pytest.mark.parametrize(
    "expected", [True, False]
)
@pytest.mark.parametrize(
    "url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"],
)
def test_admin_domyslnie_afiliuje_nowy_rekord(preauth_admin_browser, live_server, url, expected):
    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    uczelnia = mommy.make(Uczelnia, domyslnie_afiliuje=expected)

    browser = preauth_admin_browser
    browser.visit(live_server + reverse(f"admin:bpp_{url}_add"))

    browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[0].scrollIntoView()
    """)
    time.sleep(0.5)
    browser.find_by_css(".grp-add-handler")[0].click()
    time.sleep(0.5)

    v = browser.find_by_id("id_autorzy_set-0-afiliuje")
    assert v.checked == expected


@pytest.mark.parametrize(
    "afiliowany", [True, False]
)
@pytest.mark.parametrize(
    "expected", [True, False]
)
@pytest.mark.parametrize(
    "url,klasa", [("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
                  ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
                  ("patent", Patent)],
)
@pytest.mark.django_db(transaction=True)
def test_admin_domyslnie_afiliuje_istniejacy_rekord(
        preauth_admin_browser,
        live_server,
        url,
        klasa,
        expected,
        afiliowany):
    # twórz nowy obiekt, nie używaj z fixtury, bo db i transactional_db
    uczelnia = mommy.make(Uczelnia, domyslnie_afiliuje=expected)
    autor = mommy.make(Autor, nazwisko="Kowal", imiona="Ski")
    jednostka = mommy.make(Jednostka, nazwa="Lol", skrot="WT")
    wydawnictwo = mommy.make(klasa, tytul_oryginalny="test")
    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=TO_AUTOR)
    wa = wydawnictwo.dodaj_autora(autor, jednostka, zapisany_jako="Wutlolski")
    wa.afiliowany = afiliowany
    wa.save()

    browser = preauth_admin_browser
    browser.visit(live_server + reverse(f"admin:bpp_{url}_change",
                                        args=(wydawnictwo.pk,)))

    browser.execute_script("""
    document.getElementsByClassName("grp-add-handler")[1].scrollIntoView()
    """)
    time.sleep(0.5)
    browser.find_by_css(".grp-add-handler")[1].click()
    time.sleep(0.5)

    v = browser.find_by_id("id_autorzy_set-1-afiliuje")
    assert v.checked == expected
