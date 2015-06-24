# -*- encoding: utf-8 -*-
from datetime import datetime
import json
import time
import os

from django.core.urlresolvers import reverse
import django_webtest

from model_mommy import mommy
import pytest

from bpp.models.autor import Autor, Tytul
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Uczelnia, Wydzial, Jednostka
from bpp.models.system import Jezyk, Charakter_Formalny, Typ_KBN, Status_Korekty
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo

NORMAL_DJANGO_USER_LOGIN = 'test_login_bpp'
NORMAL_DJANGO_USER_PASSWORD = 'test_password'

from django.conf import settings


def pytest_configure(config):
    setattr(settings, 'CELERY_ALWAYS_EAGER', True)


@pytest.fixture
def normal_django_user(request, db, django_user_model):  # , django_username_field):
    """
    A normal Django user
    """
    UserModel = django_user_model
    # username_field = django_username_field

    try:
        obj = UserModel.objects.get(username=NORMAL_DJANGO_USER_LOGIN)
    except UserModel.DoesNotExist:
        obj = UserModel.objects.create_user(
            username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD)

    def fin():
        obj.delete()

    return obj


def _preauth_session_id_helper(username, password, client, browser, live_server, django_user_model,
                               django_username_field):
    client.login(username=username, password=password)
    browser.visit(live_server + '/favicon.ico')
    browser.cookies.add({'sessionid': client.cookies['sessionid'].value})
    browser.visit(live_server + '/')
    browser.authorized_user = django_user_model.objects.get(**{django_username_field: username})
    return browser


@pytest.fixture
def preauth_browser(normal_django_user, client, browser, live_server, django_user_model, django_username_field):
    return _preauth_session_id_helper(
        NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD, client,
        browser, live_server, django_user_model, django_username_field)


@pytest.fixture
def preauth_admin_browser(admin_user, client, browser, live_server, django_user_model, django_username_field):
    return _preauth_session_id_helper('admin', 'password', client, browser, live_server, django_user_model,
                                      django_username_field)


@pytest.fixture
def uczelnia(db):
    return Uczelnia.objects.get_or_create(skrot='TE', nazwa='Testowa uczelnia')[0]


def _wydzial_maker(nazwa, skrot, uczelnia, **kwargs):
    return Wydzial.objects.get_or_create(uczelnia=uczelnia, skrot=skrot, nazwa=nazwa, **kwargs)[0]


@pytest.fixture
def wydzial_maker(db):
    return _wydzial_maker


@pytest.fixture(scope="function")
def wydzial(uczelnia, db):
    return _wydzial_maker(uczelnia=uczelnia, skrot='W1', nazwa=u'Wydział Testowy I')


def _autor_maker(imiona, nazwisko, tytul="dr. ", **kwargs):
    tytul = Tytul.objects.get_or_create(skrot=tytul, nazwa=tytul)[0]
    return Autor.objects.get_or_create(tytul=tytul, imiona=imiona, nazwisko=nazwisko, **kwargs)[0]


@pytest.fixture
def autor_maker(db):
    return _autor_maker


@pytest.fixture(scope="function")
def autor_jan_nowak(db):
    return _autor_maker(imiona="Jan", nazwisko="Nowak")

@pytest.fixture(scope="function")
def autor(db):
    return mommy.make(Autor)

@pytest.fixture(scope="function")
def autor_jan_kowalski(db):
    return _autor_maker(imiona="Jan", nazwisko="Kowalski", tytul="prof. dr hab. n. med.")


def _jednostka_maker(nazwa, skrot, wydzial, **kwargs):
    return Jednostka.objects.get_or_create(nazwa=nazwa, skrot=skrot, wydzial=wydzial, **kwargs)[0]


@pytest.fixture(scope="function")
def jednostka(wydzial, db):
    return _jednostka_maker("Jednostka Uczelni", skrot="Jedn. Ucz.", wydzial=wydzial)


@pytest.fixture
def jednostka_maker(db):
    return _jednostka_maker


def _zrodlo_maker(nazwa, skrot, **kwargs):
    return mommy.make(Zrodlo, nazwa=nazwa, skrot=skrot, **kwargs)


@pytest.fixture
def zrodlo_maker(db):
    return _zrodlo_maker


@pytest.fixture(scope="function")
def zrodlo(db):
    return _zrodlo_maker(nazwa=u'Testowe Źródło', skrot='Test. Źr.')


def set_default(varname, value, dct):
    if varname not in dct:
        dct[varname] = value


def _wydawnictwo_maker(klass, **kwargs):
    if 'rok' not in kwargs:
        kwargs['rok'] = datetime.now().date().year

    c = time.time()
    kl = str(klass).split('.')[-1].replace("'>", "")

    kw_wyd = dict(
        tytul="Tytul %s %s" % (kl, c),
        tytul_oryginalny="Tytul oryginalny %s %s" % (kl, c),
        uwagi="Uwagi %s %s" % (kl, c),
        szczegoly='Szczegóły %s %s' % (kl, c))

    if klass == Patent:
        del kw_wyd['tytul']

    for key, value in kw_wyd.items():
        set_default(key, value, kwargs)

    return mommy.make(klass, **kwargs)


def _wydawnictwo_ciagle_maker(**kwargs):
    if 'zrodlo' not in kwargs:
        set_default('zrodlo', _zrodlo_maker(nazwa=u'Źrodło Ciągłego Wydawnictwa', skrot=u'Źród. Ciąg. Wyd.'), kwargs)

    set_default('informacje', 'zrodlo-informacje', kwargs)
    set_default('issn', '123-IS-SN-34', kwargs)

    return _wydawnictwo_maker(Wydawnictwo_Ciagle, **kwargs)


@pytest.fixture
def wydawnictwo_ciagle_maker(db):
    return _wydawnictwo_ciagle_maker


@pytest.fixture(scope="function")
def wydawnictwo_ciagle(db):
    return _wydawnictwo_ciagle_maker()


def _zwarte_base_maker(klass, **kwargs):
    if klass not in [Praca_Doktorska, Praca_Habilitacyjna, Patent]:
        set_default('liczba_znakow_wydawniczych', 31337, kwargs)

    set_default('informacje', 'zrodlo-informacje dla zwarte', kwargs)

    if klass not in [Patent]:
        set_default('miejsce_i_rok', 'Lublin %s' % datetime.now().date().year, kwargs)
        set_default('wydawnictwo', 'Wydawnictwo FOLIUM', kwargs)
        set_default('isbn', '123-IS-BN-34', kwargs)
        set_default('redakcja', 'Redakcja', kwargs)

    return _wydawnictwo_maker(klass, **kwargs)


def _zwarte_maker(**kwargs):
    return _zwarte_base_maker(Wydawnictwo_Zwarte, **kwargs)


@pytest.fixture(scope="function")
def wydawnictwo_zwarte(db):
    return _zwarte_maker(tytul_oryginalny=u'Wydawnictwo Zwarte ĄćłłóńŹ')


@pytest.fixture
def zwarte_maker(db):
    return _zwarte_maker


def _habilitacja_maker(**kwargs):
    Charakter_Formalny.objects.get_or_create(nazwa='habilitacja', skrot='H')
    return _zwarte_base_maker(Praca_Habilitacyjna, **kwargs)


@pytest.fixture(scope="function")
def habilitacja(jednostka, db):
    return _habilitacja_maker(tytul_oryginalny=u'Praca habilitacyjna', jednostka=jednostka)


@pytest.fixture
def habilitacja_maker(db):
    return _habilitacja_maker


def _doktorat_maker(**kwargs):
    Charakter_Formalny.objects.get_or_create(nazwa='doktorat', skrot='D')
    return _zwarte_base_maker(Praca_Doktorska, **kwargs)


@pytest.fixture(scope="function")
def doktorat(jednostka, db):
    return _doktorat_maker(tytul_oryginalny=u'Praca doktorska', jednostka=jednostka)


@pytest.fixture
def doktorat_maker(db):
    return _doktorat_maker


def _patent_maker(**kwargs):
    Charakter_Formalny.objects.get_or_create(nazwa='Patent', skrot='PAT')
    Typ_KBN.objects.get_or_create(nazwa="Praca Oryginalna", skrot='PO')
    Jezyk.objects.get_or_create(nazwa="polski", skrot='pol.')

    return _zwarte_base_maker(Patent, **kwargs)


@pytest.fixture
def patent(db):
    return _patent_maker(tytul_oryginalny=u'PATENT!')


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


@pytest.fixture(scope='function')
def webtest_app(request):
    wtm = django_webtest.WebTestMixin()
    wtm._patch_settings()
    request.addfinalizer(wtm._unpatch_settings)
    return django_webtest.DjangoTestApp()


def _webtest_login(webtest_app, username, password, login_form='login_form'):
    form = webtest_app.get(reverse(login_form)).form
    form['username'] = username  # normal_django_user.username
    form['password'] = password  # NORMAL_DJANGO_USER_PASSWORD
    res = form.submit().follow()
    assert res.context['user'].username == username  # normal_django_user.username
    return webtest_app


@pytest.fixture(scope='function')
def preauth_webtest_app(webtest_app, normal_django_user):
    return _webtest_login(webtest_app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD)


@pytest.fixture(scope='function')
def preauth_webtest_admin_app(webtest_app, admin_user):
    return _webtest_login(webtest_app, 'admin', 'password')


@pytest.fixture
def jezyki(db):
    Jezyk.objects.get_or_create(nazwa='angielski', skrot='ang.')
    Jezyk.objects.get_or_create(nazwa='polski', skrot='pol.')
    return dict([(x.skrot, x) for x in Jezyk.objects.all()])


@pytest.fixture
def charaktery_formalne(db):
    for elem in fixture("charakter_formalny.json"):
        Charakter_Formalny.objects.get_or_create(**elem['fields'])
    return dict([(x.skrot, x) for x in Charakter_Formalny.objects.all()])


@pytest.fixture
def typy_kbn(db):
    Typ_KBN.objects.get_or_create(nazwa='testowy', skrot='TKBN')
    return dict([(x.skrot, x) for x in Typ_KBN.objects.all()])


def fixture(name):
    return json.load(
        open(
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "bpp", "fixtures", name)
            ), "r"))


@pytest.fixture
def statusy_korekt(db):
    for elem in fixture("status_korekty.json"):
        Status_Korekty.objects.get_or_create(**elem['fields'])


@pytest.fixture
def obiekty_bpp(typy_kbn, charaktery_formalne, jezyki, statusy_korekt):
    class ObiektyBpp:
        jezyk = jezyki
        charakter_formalny = charaktery_formalne
        typ_kbn = typy_kbn
        status_korekty = Status_Korekty.objects.all()

    return ObiektyBpp

@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_dwoma_autorami(wydawnictwo_ciagle, autor_jan_kowalski, autor_jan_nowak, jednostka):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    return wydawnictwo_ciagle

def pytest_configure():
    from django.conf import settings
    settings.TESTING = True
