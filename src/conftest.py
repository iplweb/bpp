# -*- encoding: utf-8 -*-
import json
import os
import time
from datetime import datetime

import django_webtest
import pytest
import webtest
from rest_framework.test import APIClient
from selenium.webdriver.remote.webdriver import WebDriver

from bpp.tasks import aktualizuj_cache_rekordu

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_mommy import mommy

from bpp.fixtures import get_openaccess_data
from bpp.models import (
    TO_AUTOR,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Wydawca,
    Zewnetrzna_Baza_Danych,
    const,
)
from bpp.models.autor import Autor, Funkcja_Autora, Tytul
from bpp.models.const import GR_WPROWADZANIE_DANYCH
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Jednostka, Uczelnia, Wydzial
from bpp.models.system import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
)
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo

from django_bpp.selenium_util import wait_for_page_load, wait_for_websocket_connection

NORMAL_DJANGO_USER_LOGIN = "test_login_bpp"
NORMAL_DJANGO_USER_PASSWORD = "test_password"

from asgi_live_server import asgi_live_server  # noqa

from bpp.tests.util import setup_mommy

setup_mommy()


def current_rok():
    return datetime.now().date().year


@pytest.fixture
def rok():
    return current_rok()


@pytest.fixture
def dyscyplina1(db):
    return Dyscyplina_Naukowa.objects.get_or_create(
        nazwa="memetyka stosowana", kod="MS"
    )[0]


@pytest.fixture
def dyscyplina2(db):
    return Dyscyplina_Naukowa.objects.get_or_create(nazwa="druga dyscyplina", kod="DD")[
        0
    ]


@pytest.fixture
def dyscyplina3(db):
    return Dyscyplina_Naukowa.objects.get_or_create(
        nazwa="trzecia dyscyplina", kod="TD"
    )[0]


@pytest.fixture
def normal_django_user(request, db, django_user_model):  # , django_username_field):
    """
    A normal Django user
    """

    try:
        obj = django_user_model.objects.get(username=NORMAL_DJANGO_USER_LOGIN)
    except django_user_model.DoesNotExist:
        obj = django_user_model.objects.create_user(
            username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD
        )

    def fin():
        obj.delete()

    return obj


def _preauth_session_id_helper(
    username,
    password,
    client,
    browser,
    asgi_live_server,  # noqa
    django_user_model,
    django_username_field,
):
    res = client.login(username=username, password=password)
    assert res is True

    with wait_for_page_load(browser):
        browser.visit(asgi_live_server.url + "/non-existant-url")
    browser.cookies.add({"sessionid": client.cookies["sessionid"].value})
    browser.authorized_user = django_user_model.objects.get(
        **{django_username_field: username}
    )
    # with wait_for_page_load(browser):
    #    browser.reload()
    return browser


@pytest.fixture
def preauth_browser(
    normal_django_user,
    client,
    browser,
    asgi_live_server,  # noqa
    django_user_model,
    django_username_field,
):
    browser = _preauth_session_id_helper(
        NORMAL_DJANGO_USER_LOGIN,
        NORMAL_DJANGO_USER_PASSWORD,
        client,
        browser,
        asgi_live_server,
        django_user_model,
        django_username_field,
    )

    yield browser
    browser.quit()


@pytest.fixture
def preauth_asgi_browser(preauth_browser, transactional_db, asgi_live_server):  # noqa
    with wait_for_page_load(preauth_browser):
        preauth_browser.visit(asgi_live_server.url)
    wait_for_websocket_connection(preauth_browser)
    return preauth_browser


@pytest.fixture
def admin_browser(
    admin_user,
    client,
    browser,
    asgi_live_server,  # noqa
    django_user_model,
    django_username_field,
    transactional_db,
) -> WebDriver:
    browser = _preauth_session_id_helper(
        "admin",
        "password",
        client,
        browser,
        asgi_live_server,
        django_user_model,
        django_username_field,
    )
    browser.driver.set_window_size(1920, 1200)

    yield browser
    browser.execute_script("window.onbeforeunload = function(e) {};")
    browser.quit()


@pytest.fixture
def uczelnia(db):
    return Uczelnia.objects.get_or_create(skrot="TE", nazwa="Testowa uczelnia")[0]


@pytest.mark.django_db
def _wydzial_maker(nazwa, skrot, uczelnia, **kwargs):
    return Wydzial.objects.get_or_create(
        uczelnia=uczelnia, skrot=skrot, nazwa=nazwa, **kwargs
    )[0]


@pytest.mark.django_db
@pytest.fixture
def wydzial_maker(db):
    return _wydzial_maker


@pytest.mark.django_db
@pytest.fixture(scope="function")
def wydzial(uczelnia, db):
    return _wydzial_maker(uczelnia=uczelnia, skrot="W1", nazwa=u"Wydział Testowy I")


def _autor_maker(imiona, nazwisko, tytul="dr", **kwargs):
    tytul = Tytul.objects.get(skrot=tytul)
    return Autor.objects.get_or_create(
        tytul=tytul, imiona=imiona, nazwisko=nazwisko, **kwargs
    )[0]


@pytest.fixture
def autor_maker(db):
    return _autor_maker


@pytest.fixture(scope="function")
def autor_jan_nowak(db, tytuly):
    return _autor_maker(imiona="Jan", nazwisko="Nowak")


@pytest.fixture(scope="function")
def autor(db, tytuly):
    return mommy.make(Autor)


@pytest.fixture(scope="function")
def typ_odpowiedzialnosci_autor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=TO_AUTOR
    )


@pytest.fixture(scope="function")
def autor_jan_kowalski(db, tytuly):
    return _autor_maker(imiona="Jan", nazwisko="Kowalski", tytul="prof. dr hab. med.")


def _jednostka_maker(nazwa, skrot, wydzial, **kwargs):
    return Jednostka.objects.get_or_create(
        nazwa=nazwa, skrot=skrot, wydzial=wydzial, uczelnia=wydzial.uczelnia, **kwargs
    )[0]


@pytest.mark.django_db
@pytest.fixture(scope="function")
def jednostka(wydzial, db):
    return _jednostka_maker("Jednostka Uczelni", skrot="Jedn. Ucz.", wydzial=wydzial)


@pytest.mark.django_db
@pytest.fixture(scope="function")
def druga_jednostka(wydzial, db):
    return _jednostka_maker(
        "Druga Jednostka Uczelni", skrot="Dr. Jedn. Ucz.", wydzial=wydzial
    )


@pytest.mark.django_db
@pytest.fixture(scope="function")
def obca_jednostka(wydzial):
    return _jednostka_maker(
        "Obca Jednostka",
        skrot="OJ",
        wydzial=wydzial,
        skupia_pracownikow=False,
        zarzadzaj_automatycznie=False,
        widoczna=False,
        wchodzi_do_raportow=False,
    )


@pytest.fixture
def jednostka_maker():
    return _jednostka_maker


def _zrodlo_maker(nazwa, skrot, **kwargs):
    return mommy.make(Zrodlo, nazwa=nazwa, skrot=skrot, **kwargs)


@pytest.fixture
def zrodlo_maker():
    return _zrodlo_maker


@pytest.fixture(scope="function")
def zrodlo(db):
    return _zrodlo_maker(nazwa=u"Testowe Źródło", skrot="Test. Źr.")


def set_default(varname, value, dct):
    if varname not in dct:
        dct[varname] = value


def _wydawnictwo_maker(klass, **kwargs):
    if "rok" not in kwargs:
        kwargs["rok"] = current_rok()

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

    for key, value in kw_wyd.items():
        set_default(key, value, kwargs)

    return mommy.make(klass, **kwargs)


def _wydawnictwo_ciagle_maker(**kwargs):
    if "zrodlo" not in kwargs:
        set_default(
            "zrodlo",
            _zrodlo_maker(
                nazwa=u"Źrodło Ciągłego Wydawnictwa", skrot=u"Źród. Ciąg. Wyd."
            ),
            kwargs,
        )

    set_default("informacje", "zrodlo-informacje", kwargs)
    set_default("issn", "123-IS-SN-34", kwargs)

    return _wydawnictwo_maker(Wydawnictwo_Ciagle, **kwargs)


def wydawnictwo_ciagle_maker(db):
    return _wydawnictwo_ciagle_maker


@pytest.fixture(scope="function")
@pytest.mark.django_db
def wydawnictwo_ciagle(
    jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    ret = _wydawnictwo_ciagle_maker()
    return ret


def _zwarte_base_maker(klass, **kwargs):
    if klass not in [Praca_Doktorska, Praca_Habilitacyjna, Patent]:
        set_default("liczba_znakow_wydawniczych", 31337, kwargs)

    set_default("informacje", "zrodlo-informacje dla zwarte", kwargs)

    if klass not in [Patent]:
        set_default("miejsce_i_rok", "Lublin %s" % current_rok(), kwargs)
        set_default("wydawnictwo", "Wydawnictwo FOLIUM", kwargs)
        set_default("isbn", "123-IS-BN-34", kwargs)
        set_default("redakcja", "Redakcja", kwargs)

    return _wydawnictwo_maker(klass, **kwargs)


def _zwarte_maker(**kwargs):
    return _zwarte_base_maker(Wydawnictwo_Zwarte, **kwargs)


@pytest.fixture(scope="function")
def wydawnictwo_zwarte(
    jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    """
    :rtype: bpp.models.Wydawnictwo_Zwarte
    """
    return _zwarte_maker(tytul_oryginalny=u"Wydawnictwo Zwarte ĄćłłóńŹ")


@pytest.fixture
def zwarte_maker(db):
    return _zwarte_maker


@pytest.fixture
def wydawca(db):
    return Wydawca.objects.get_or_create(nazwa="Wydawca Testowy")[0]


@pytest.fixture
def alias_wydawcy(wydawca):
    return Wydawca.objects.create(nazwa="Drugi taki tam", alias_dla=wydawca)


def _habilitacja_maker(**kwargs):
    Charakter_Formalny.objects.get_or_create(nazwa="Praca habilitacyjna", skrot="H")
    return _zwarte_base_maker(Praca_Habilitacyjna, **kwargs)


@pytest.fixture(scope="function")
def habilitacja(jednostka, db, charaktery_formalne, jezyki, typy_odpowiedzialnosci):
    return _habilitacja_maker(
        tytul_oryginalny=u"Praca habilitacyjna", jednostka=jednostka
    )


@pytest.fixture
def praca_habilitacyjna(
    habilitacja,
) -> Praca_Habilitacyjna:
    return habilitacja


@pytest.fixture
def habilitacja_maker(db):
    return _habilitacja_maker


def _doktorat_maker(**kwargs):
    return _zwarte_base_maker(Praca_Doktorska, **kwargs)


@pytest.fixture(scope="function")
def doktorat(jednostka, charaktery_formalne, jezyki, typy_odpowiedzialnosci):
    return _doktorat_maker(tytul_oryginalny=u"Praca doktorska", jednostka=jednostka)


@pytest.fixture(scope="function")
def praca_doktorska(doktorat):
    return doktorat


@pytest.fixture
def doktorat_maker(db):
    return _doktorat_maker


def _patent_maker(**kwargs):
    return _zwarte_base_maker(Patent, **kwargs)


@pytest.fixture
def patent(db, typy_odpowiedzialnosci, jezyki, charaktery_formalne, typy_kbn):
    return _patent_maker(tytul_oryginalny=u"PATENT!")


@pytest.fixture
def patent_maker(db):
    return _patent_maker


# def _lookup_fun(klass):
#     def fun(skrot):
#         return klass.objects.filter(skrot=skrot)
#     return fun
#
#
# typ_kbn = _lookup_fun(Typ_KBN)
# jezyk = _lookup_fun(Jezyk)
# charakter = _lookup_fun(Charakter_Formalny)


@pytest.fixture(scope="function")
def webtest_app(request):
    wtm = django_webtest.WebTestMixin()
    wtm._patch_settings()
    request.addfinalizer(wtm._unpatch_settings)
    return django_webtest.DjangoTestApp()


def _webtest_login(webtest_app, username, password, login_form="login_form"):
    form = webtest_app.get(reverse(login_form)).form
    form["username"] = username  # normal_django_user.username
    form["password"] = password  # NORMAL_DJANGO_USER_PASSWORD
    res = form.submit().maybe_follow()
    assert res.context["user"].username == username  # normal_django_user.username
    return webtest_app


@pytest.fixture(scope="function")
def wprowadzanie_danych_user(normal_django_user):
    from django.contrib.auth.models import Group

    grp = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0]
    normal_django_user.groups.add(grp)
    return normal_django_user


@pytest.fixture(scope="function")
def app(webtest_app, normal_django_user) -> webtest.app.TestApp:
    return _webtest_login(
        webtest_app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD
    )


@pytest.fixture(scope="function")
def wd_app(webtest_app, wprowadzanie_danych_user):
    return _webtest_login(
        webtest_app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD
    )


@pytest.fixture(scope="function")
def admin_app(webtest_app, admin_user):
    """
    :rtype: django_webtest.DjangoTestApp
    """

    return _webtest_login(webtest_app, "admin", "password")


def fixture(name):
    return json.load(
        open(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "bpp", "fixtures", name)
            ),
            "rb",
        )
    )


@pytest.fixture(scope="function")
def typy_odpowiedzialnosci(db):
    for elem in fixture("typ_odpowiedzialnosci_v2.json"):
        Typ_Odpowiedzialnosci.objects.get_or_create(pk=elem["pk"], **elem["fields"])
    return dict([(x.skrot, x) for x in Typ_Odpowiedzialnosci.objects.all()])


@pytest.fixture(scope="function")
def tytuly():
    for elem in fixture("tytul.json"):
        Tytul.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def jezyki(db):
    pl, created = Jezyk.objects.get_or_create(pk=1, skrot="pol.", nazwa="polski")
    pl.skrot_dla_pbn = "PL"
    pl.save()
    assert pl.pk == 1

    ang, created = Jezyk.objects.get_or_create(pk=2, skrot="ang.", nazwa="angielski")
    ang.skrot_dla_pbn = "EN"
    ang.save()
    assert ang.pk == 2

    for elem in fixture("jezyk.json"):
        Jezyk.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def charaktery_formalne():
    Charakter_Formalny.objects.all().delete()
    for elem in fixture("charakter_formalny.json"):
        Charakter_Formalny.objects.get_or_create(pk=elem["pk"], **elem["fields"])

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_ksp.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    chf_ksp.charakter_ogolny = const.CHARAKTER_OGOLNY_KSIAZKA
    chf_ksp.charakter_sloty = const.CHARAKTER_SLOTY_KSIAZKA
    chf_ksp.nazwa_w_primo = "Książka"
    chf_ksp.save()

    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")
    chf_roz.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    chf_ksp.charakter_ogolny = const.CHARAKTER_OGOLNY_ROZDZIAL
    chf_roz.charakter_sloty = const.CHARAKTER_SLOTY_ROZDZIAL
    chf_roz.save()

    return dict([(x.skrot, x) for x in Charakter_Formalny.objects.all()])


@pytest.fixture(scope="function")
def ksiazka_polska(charaktery_formalne):
    return charaktery_formalne["KSP"]


@pytest.fixture(scope="function")
def artykul_w_czasopismie(charaktery_formalne):
    return charaktery_formalne["AC"]


@pytest.fixture(scope="function")
def typy_kbn():
    for elem in fixture("typ_kbn.json"):
        Typ_KBN.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def statusy_korekt():
    for elem in fixture("status_korekty.json"):
        Status_Korekty.objects.get_or_create(pk=elem["pk"], **elem["fields"])
    return {status.nazwa: status for status in Status_Korekty.objects.all()}


@pytest.fixture(scope="function")
def przed_korekta(statusy_korekt):
    return statusy_korekt["przed korektą"]


@pytest.fixture(scope="function")
def po_korekcie(statusy_korekt):
    return statusy_korekt["po korekcie"]


@pytest.fixture(scope="function")
def funkcje_autorow():
    for elem in fixture("funkcja_autora.json"):
        Funkcja_Autora.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def standard_data(
    typy_odpowiedzialnosci,
    tytuly,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    funkcje_autorow,
):
    pass


@pytest.mark.django_db
@pytest.fixture(scope="function")
def openaccess_data():
    from django.contrib.contenttypes.models import ContentType

    for model_name, skrot, nazwa in get_openaccess_data():
        klass = ContentType.objects.get_by_natural_key("bpp", model_name).model_class()
        klass.objects.get_or_create(nazwa=nazwa, skrot=skrot)


@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_autorem(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    return wydawnictwo_ciagle


@pytest.fixture(scope="function")
def wydawnictwo_zwarte_z_autorem(wydawnictwo_zwarte, autor_jan_kowalski, jednostka):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    return wydawnictwo_zwarte


@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_dwoma_autorami(
    wydawnictwo_ciagle_z_autorem, autor_jan_nowak, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_ciagle_z_autorem.dodaj_autora(autor_jan_nowak, jednostka)
    return wydawnictwo_ciagle_z_autorem


def pytest_configure():
    from django.conf import settings

    if hasattr(settings, "RAVEN_CONFIG"):
        del settings.RAVEN_CONFIG  # setattr(settings, "RAVEN_CONFIG", None)

    settings.TESTING = True
    settings.CELERY_ALWAYS_EAGER = True
    settings.CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

    from bpp.models.cache import Autorzy, Rekord

    Rekord._meta.managed = True
    Autorzy._meta.managed = True


# @pytest.fixture(scope="session")
# def splinter_driver_kwargs(splinter_webdriver):
#    if splinter_webdriver == "remote":
#        from selenium import webdriver

#        chrome_op = webdriver.ChromeOptions()
#        chrome_op.add_argument("--disable-extensions")
#        chrome_op.add_argument("--disable-extensions-file-access-check")
#        chrome_op.add_argument("--disable-extensions-http-throttling")
#        chrome_op.add_argument("--disable-infobars")
#        chrome_op.add_argument("--enable-automation")
#        chrome_op.add_argument("--start-maximized")
#        chrome_op.add_experimental_option('prefs', {
#            'credentials_enable_service': False,
#            'profile': {
#                'password_manager_enabled': False
#            }
#        })
#        return {'browser': "chrome",
#                "desired_capabilities": chrome_op.to_capabilities()}

collect_ignore = [os.path.join(os.path.dirname(__file__), "media")]

import os

import pytest


@pytest.fixture
def praca_z_dyscyplina(wydawnictwo_ciagle_z_autorem, dyscyplina1, rok, db):
    wydawnictwo_ciagle_z_autorem.punkty_kbn = 5
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    Autor_Dyscyplina.objects.create(
        autor=wca.autor, rok=wca.rekord.rok, dyscyplina_naukowa=dyscyplina1
    )
    wca.dyscyplina_naukowa = dyscyplina1
    wca.save()
    aktualizuj_cache_rekordu(wydawnictwo_ciagle_z_autorem)
    return wydawnictwo_ciagle_z_autorem


@pytest.fixture
def api_client(client):
    return APIClient()


@pytest.fixture
def baza_wos():
    return Zewnetrzna_Baza_Danych.objects.get_or_create(
        nazwa="Web of Science", skrot="WOS"
    )[0]


from asgi_live_server import asgi_live_server  # noqa


@pytest.fixture
def wydawnictwo_zwarte_przed_korekta(statusy_korekt):
    return mommy.make(
        Wydawnictwo_Zwarte, status_korekty=statusy_korekt["przed korektą"]
    )


@pytest.fixture
def wydawnictwo_zwarte_w_trakcie_korekty(statusy_korekt):
    return mommy.make(
        Wydawnictwo_Zwarte, status_korekty=statusy_korekt["w trakcie korekty"]
    )


@pytest.fixture
def wydawnictwo_zwarte_po_korekcie(statusy_korekt):
    return mommy.make(Wydawnictwo_Zwarte, status_korekty=statusy_korekt["po korekcie"])


@pytest.fixture
def ksiazka(wydawnictwo_zwarte, ksiazka_polska) -> "Wydawnictwo_Zwarte":
    wydawnictwo_zwarte.charakter_formalny = ksiazka_polska
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


@pytest.fixture
def artykul(wydawnictwo_ciagle, artykul_w_czasopismie):
    wydawnictwo_ciagle.charakter_formalny = artykul_w_czasopismie
    wydawnictwo_ciagle.save()
    return wydawnictwo_ciagle
