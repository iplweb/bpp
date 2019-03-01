# -*- encoding: utf-8 -*-
import json
import os
import time
from datetime import datetime

import django_webtest
import pytest
from django.core.urlresolvers import reverse
from model_mommy import mommy

from bpp.fixtures import get_openaccess_data
from bpp.models import TO_AUTOR
from bpp.models.autor import Autor, Tytul, Funkcja_Autora
from bpp.models.const import GR_WPROWADZANIE_DANYCH
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Uczelnia, Wydzial, Jednostka
from bpp.models.system import Jezyk, Charakter_Formalny, Typ_KBN, \
    Status_Korekty, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from django_bpp.selenium_util import wait_for_page_load

NORMAL_DJANGO_USER_LOGIN = 'test_login_bpp'
NORMAL_DJANGO_USER_PASSWORD = 'test_password'

from django.conf import settings
from bpp.tests.util import setup_mommy

setup_mommy()


def pytest_configure(config):
    setattr(settings, 'CELERY_ALWAYS_EAGER', True)

def current_rok():
    return datetime.now().date().year

@pytest.fixture
def rok():
    return current_rok()


@pytest.fixture
def normal_django_user(request, db,
                       django_user_model):  # , django_username_field):
    """
    A normal Django user
    """

    try:
        obj = django_user_model.objects.get(username=NORMAL_DJANGO_USER_LOGIN)
    except django_user_model.DoesNotExist:
        obj = django_user_model.objects.create_user(
            username=NORMAL_DJANGO_USER_LOGIN,
            password=NORMAL_DJANGO_USER_PASSWORD)

    def fin():
        obj.delete()

    return obj


def _preauth_session_id_helper(username, password, client, browser,
                               nginx_live_server, django_user_model,
                               django_username_field):

    res = client.login(username=username, password=password)
    assert res is True

    with wait_for_page_load(browser):
        browser.visit(nginx_live_server.url + "/")
    browser.cookies.add({'sessionid': client.cookies['sessionid'].value})
    browser.authorized_user = django_user_model.objects.get(
        **{django_username_field: username})
    with wait_for_page_load(browser):
        browser.reload()
    return browser


@pytest.fixture
def preauth_browser(normal_django_user, client, browser, nginx_live_server,
                    django_user_model, django_username_field, settings):
    browser = _preauth_session_id_helper(
        NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD, client,
        browser, nginx_live_server, django_user_model, django_username_field)

    settings.NOTIFICATIONS_HOST = nginx_live_server.host
    settings.NOTIFICATIONS_PORT = nginx_live_server.port

    yield browser
    browser.quit()


@pytest.fixture
def preauth_admin_browser(admin_user, client, browser, nginx_live_server,
                          django_user_model, django_username_field, settings):
    browser = _preauth_session_id_helper('admin', 'password', client, browser,
                                         nginx_live_server, django_user_model,
                                         django_username_field)
    settings.NOTIFICATIONS_HOST = nginx_live_server.host
    settings.NOTIFICATIONS_PORT = nginx_live_server.port
    yield browser
    browser.execute_script("window.onbeforeunload = function(e) {};")
    browser.quit()


@pytest.fixture
def uczelnia(db):
    return \
        Uczelnia.objects.get_or_create(skrot='TE', nazwa='Testowa uczelnia')[0]


@pytest.mark.django_db
def _wydzial_maker(nazwa, skrot, uczelnia, **kwargs):
    return \
        Wydzial.objects.get_or_create(uczelnia=uczelnia, skrot=skrot, nazwa=nazwa,
                                      **kwargs)[0]


@pytest.mark.django_db
@pytest.fixture
def wydzial_maker(db):
    return _wydzial_maker


@pytest.mark.django_db
@pytest.fixture(scope="function")
def wydzial(uczelnia, db):
    return _wydzial_maker(uczelnia=uczelnia, skrot='W1',
                          nazwa=u'Wydział Testowy I')


def _autor_maker(imiona, nazwisko, tytul="dr", **kwargs):
    tytul = Tytul.objects.get(skrot=tytul)
    return \
        Autor.objects.get_or_create(tytul=tytul, imiona=imiona, nazwisko=nazwisko,
                                    **kwargs)[0]


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
        skrot="aut.", nazwa="autor",
        typ_ogolny=TO_AUTOR
    )

@pytest.fixture(scope="function")
def autor_jan_kowalski(db, tytuly):
    return _autor_maker(imiona="Jan", nazwisko="Kowalski",
                        tytul="prof. dr hab. med.")


def _jednostka_maker(nazwa, skrot, wydzial, **kwargs):
    return \
        Jednostka.objects.get_or_create(nazwa=nazwa, skrot=skrot,
                                        wydzial=wydzial,
                                        uczelnia=wydzial.uczelnia, **kwargs)[
            0]


@pytest.mark.django_db
@pytest.fixture(scope="function")
def jednostka(wydzial, db):
    return _jednostka_maker("Jednostka Uczelni", skrot="Jedn. Ucz.",
                            wydzial=wydzial)


@pytest.mark.django_db
@pytest.fixture(scope="function")
def druga_jednostka(wydzial, db):
    return _jednostka_maker("Druga Jednostka Uczelni", skrot="Dr. Jedn. Ucz.",
                            wydzial=wydzial)


@pytest.mark.django_db
@pytest.fixture(scope="function")
def obca_jednostka(wydzial):
    return _jednostka_maker("Obca Jednostka", skrot="OJ", wydzial=wydzial,
                            skupia_pracownikow=False,
                            zarzadzaj_automatycznie=False, widoczna=False,
                            wchodzi_do_raportow=False)


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
    return _zrodlo_maker(nazwa=u'Testowe Źródło', skrot='Test. Źr.')


def set_default(varname, value, dct):
    if varname not in dct:
        dct[varname] = value


def _wydawnictwo_maker(klass, **kwargs):
    if 'rok' not in kwargs:
        kwargs['rok'] = current_rok()

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
        set_default('zrodlo',
                    _zrodlo_maker(nazwa=u'Źrodło Ciągłego Wydawnictwa',
                                  skrot=u'Źród. Ciąg. Wyd.'), kwargs)

    set_default('informacje', 'zrodlo-informacje', kwargs)
    set_default('issn', '123-IS-SN-34', kwargs)

    return _wydawnictwo_maker(Wydawnictwo_Ciagle, **kwargs)


def wydawnictwo_ciagle_maker(db):
    return _wydawnictwo_ciagle_maker


@pytest.fixture(scope="function")
def wydawnictwo_ciagle(jezyki, charaktery_formalne, typy_kbn,
                       statusy_korekt, typy_odpowiedzialnosci):
    ret = _wydawnictwo_ciagle_maker()
    return ret


def _zwarte_base_maker(klass, **kwargs):
    if klass not in [Praca_Doktorska, Praca_Habilitacyjna, Patent]:
        set_default('liczba_znakow_wydawniczych', 31337, kwargs)

    set_default('informacje', 'zrodlo-informacje dla zwarte', kwargs)

    if klass not in [Patent]:
        set_default('miejsce_i_rok', 'Lublin %s' % current_rok(), kwargs)
        set_default('wydawnictwo', 'Wydawnictwo FOLIUM', kwargs)
        set_default('isbn', '123-IS-BN-34', kwargs)
        set_default('redakcja', 'Redakcja', kwargs)

    return _wydawnictwo_maker(klass, **kwargs)


def _zwarte_maker(**kwargs):
    return _zwarte_base_maker(Wydawnictwo_Zwarte, **kwargs)


@pytest.fixture(scope="function")
def wydawnictwo_zwarte(jezyki, charaktery_formalne, typy_kbn,
                       statusy_korekt, typy_odpowiedzialnosci):
    return _zwarte_maker(tytul_oryginalny=u'Wydawnictwo Zwarte ĄćłłóńŹ')


@pytest.fixture
def zwarte_maker(db):
    return _zwarte_maker


def _habilitacja_maker(**kwargs):
    Charakter_Formalny.objects.get_or_create(nazwa='Praca habilitacyjna',
                                             skrot='H')
    return _zwarte_base_maker(Praca_Habilitacyjna, **kwargs)


@pytest.fixture(scope="function")
def habilitacja(jednostka, db, charaktery_formalne, jezyki, typy_odpowiedzialnosci):
    return _habilitacja_maker(tytul_oryginalny=u'Praca habilitacyjna',
                              jednostka=jednostka)


@pytest.fixture
def habilitacja_maker(db):
    return _habilitacja_maker


def _doktorat_maker(**kwargs):
    return _zwarte_base_maker(Praca_Doktorska, **kwargs)


@pytest.fixture(scope="function")
def doktorat(jednostka, charaktery_formalne, jezyki, typy_odpowiedzialnosci):
    return _doktorat_maker(tytul_oryginalny=u'Praca doktorska',
                           jednostka=jednostka)


@pytest.fixture
def doktorat_maker(db):
    return _doktorat_maker


def _patent_maker(**kwargs):
    return _zwarte_base_maker(Patent, **kwargs)


@pytest.fixture
def patent(db, typy_odpowiedzialnosci, jezyki, charaktery_formalne, typy_kbn):
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
    assert res.context[
               'user'].username == username  # normal_django_user.username
    return webtest_app


@pytest.fixture(scope='function')
def wprowadzanie_danych_user(normal_django_user):
    from django.contrib.auth.models import Group
    grp = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0]
    normal_django_user.groups.add(grp)
    return normal_django_user


@pytest.fixture(scope='function')
def app(webtest_app, normal_django_user):
    return _webtest_login(webtest_app, NORMAL_DJANGO_USER_LOGIN,
                          NORMAL_DJANGO_USER_PASSWORD)


@pytest.fixture(scope='function')
def wd_app(webtest_app, wprowadzanie_danych_user):
    return _webtest_login(webtest_app, NORMAL_DJANGO_USER_LOGIN,
                          NORMAL_DJANGO_USER_PASSWORD)


@pytest.fixture(scope='function')
def admin_app(webtest_app, admin_user):
    """
    :rtype: django_webtest.DjangoTestApp
    """

    return _webtest_login(webtest_app, 'admin', 'password')


def fixture(name):
    return json.load(
        open(
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "bpp", "fixtures", name)
            ), "rb"))


@pytest.fixture(scope='function')
def typy_odpowiedzialnosci():
    for elem in fixture("typ_odpowiedzialnosci_v2.json"):
        Typ_Odpowiedzialnosci.objects.get_or_create(pk=elem['pk'], **elem['fields'])


@pytest.fixture(scope='function')
def tytuly():
    for elem in fixture("tytul.json"):
        Tytul.objects.get_or_create(pk=elem['pk'], **elem['fields'])


@pytest.fixture(scope='function')
def jezyki():
    pl, created = Jezyk.objects.get_or_create(
        pk=1, skrot='pol.', nazwa='polski')
    pl.skrot_dla_pbn = 'PL'
    pl.save()
    assert pl.pk == 1

    ang, created = Jezyk.objects.get_or_create(
        pk=2, skrot='ang.', nazwa='angielski')
    ang.skrot_dla_pbn = 'EN'
    ang.save()
    assert ang.pk == 2

    for elem in fixture("jezyk.json"):
        Jezyk.objects.get_or_create(pk=elem['pk'], **elem['fields'])


@pytest.fixture(scope='function')
def charaktery_formalne():
    Charakter_Formalny.objects.all().delete()
    for elem in fixture("charakter_formalny.json"):
        Charakter_Formalny.objects.get_or_create(pk=elem['pk'], **elem['fields'])

    chf_ksp = Charakter_Formalny.objects.get(skrot='KSP')
    chf_ksp.ksiazka_pbn = True
    chf_ksp.save()

    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")
    chf_roz.rozdzial_pbn = True
    chf_roz.save()


@pytest.fixture(scope='function')
def typy_kbn():
    for elem in fixture("typ_kbn.json"):
        Typ_KBN.objects.get_or_create(pk=elem['pk'], **elem['fields'])


@pytest.fixture(scope='function')
def statusy_korekt():
    for elem in fixture("status_korekty.json"):
        Status_Korekty.objects.get_or_create(pk=elem['pk'], **elem['fields'])


@pytest.fixture(scope='function')
def funkcje_autorow():
    for elem in fixture("funkcja_autora.json"):
        Funkcja_Autora.objects.get_or_create(pk=elem['pk'], **elem['fields'])


@pytest.fixture(scope='function')
def standard_data(typy_odpowiedzialnosci, tytuly, jezyki,
                  charaktery_formalne, typy_kbn, statusy_korekt,
                  funkcje_autorow):
    pass


@pytest.mark.django_db
@pytest.fixture(scope='function')
def openaccess_data():
    from django.contrib.contenttypes.models import ContentType
    for model_name, skrot, nazwa in get_openaccess_data():
        klass = ContentType.objects.get_by_natural_key(
            "bpp", model_name).model_class()
        klass.objects.get_or_create(nazwa=nazwa, skrot=skrot)


@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_autorem(wydawnictwo_ciagle, autor_jan_kowalski,
                                 jednostka, typy_odpowiedzialnosci):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    return wydawnictwo_ciagle


@pytest.fixture(scope="function")
def wydawnictwo_zwarte_z_autorem(wydawnictwo_zwarte, autor_jan_kowalski,
                                 jednostka):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    return wydawnictwo_zwarte


@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_dwoma_autorami(wydawnictwo_ciagle_z_autorem,
                                        autor_jan_nowak, jednostka,
                                        typy_odpowiedzialnosci):
    wydawnictwo_ciagle_z_autorem.dodaj_autora(autor_jan_nowak, jednostka)
    return wydawnictwo_ciagle_z_autorem


def pytest_configure():
    from django.conf import settings
    if hasattr(settings, "RAVEN_CONFIG"):
        del settings.RAVEN_CONFIG  # setattr(settings, "RAVEN_CONFIG", None)

    settings.TESTING = True
    settings.CELERY_ALWAYS_EAGER = True
    settings.CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

    from bpp.models.cache import Rekord, Autorzy
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

collect_ignore = [
    os.path.join(os.path.dirname(__file__), "media")
]

import subprocess
import os
import pytest
from pytest_nginx.factories import init_nginx, get_random_port, wait_for_socket_check_processes, \
    NginxProcess, daemon


@pytest.fixture(scope="session")
def nginx_server_root(tmpdir_factory):
    return tmpdir_factory.mktemp("nginx-server-root")


DEFAULT_NGINX_TEMPLATE = """
daemon off;
pid %TMPDIR%/nginx.pid;
error_log %TMPDIR%/error.log;
worker_processes auto;
worker_cpu_affinity auto;

events {
    worker_connections  1024;
}

http {
    default_type  application/octet-stream;
    access_log off;
    sendfile on;
    charset utf-8;
    push_stream_shared_memory_size 32M;
	tcp_nopush on;
	tcp_nodelay on;

    server {
        listen       %PORT%;
        server_name  %HOST%;

        location @proxy_to_app {
            proxy_pass http://%LIVESERVER_HOST%:%LIVESERVER_PORT%;

            proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header  X-Forwarded-Host $server_name;
            proxy_set_header  X-Real-IP $remote_addr;
            proxy_set_header  X-Scheme $scheme;
            proxy_set_header  Host $http_host;

            proxy_redirect    off;
        }

        # the /auth location will send a subrequest to Django each time someone wants
        # to subscribe to a nginx-push-stream channel (see /ws/ location definition below)
        location = /auth {
            internal;

            proxy_pass http://%LIVESERVER_HOST%:%LIVESERVER_PORT%;

            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header X-Original-URI $request_uri;
            proxy_set_header Cookie $http_cookie;
        }

        location /channels-stats {
            push_stream_channels_statistics;
            push_stream_channels_path               $arg_id;
        }

        location /pub {
            push_stream_publisher admin;
            push_stream_channels_path               $arg_id;
        }

        location ~ /sub/(.*) {
            push_stream_subscriber;
            push_stream_channels_path                   $1;
        }

        location ~ /ws/(.*) {
            # mpasternak 17.02.2019 na ten moment NIE używaj tego /auth do
            # momentu podpięcia django-reciprocity. Potem włączyć.
            # auth_request                                /auth;

            push_stream_subscriber websocket;
            push_stream_channels_path                   $1;
            push_stream_message_template                "{\\"id\\":~id~,\\"channel\\":\\"~channel~\\",\\"text\\":~text~, \\"time\\":\\"~time~\\", \\"eventid\\":\\"~event-id~\\"}";

        }
        location ~ /ev/(.*) {
            push_stream_subscriber                      eventsource;
            push_stream_channels_path                   $1;
            push_stream_message_template                "{\\"id\\":~id~,\\"channel\\":\\"~channel~\\",\\"text\\":~text~}";
        }

        root /var/www/html;

        # Add index.php to the list if you are using PHP
        index index.html index.htm index.nginx-debian.html;

        location / {
            try_files $uri @proxy_to_app;
        }
    }
}
"""


def nginx_liveserver_proc(
        server_root_fixture_name="nginx_server_root",
        host=None, port=None, nginx_exec=None, nginx_params=None,
        config_template=None, template_str=DEFAULT_NGINX_TEMPLATE,
        template_extra_params=None):
    @pytest.fixture(scope='session')
    def nginx_proc_fixture(request, tmpdir_factory, live_server):
        nonlocal host, port, nginx_exec, nginx_params, config_template, template_extra_params, template_str

        server_root = request.getfixturevalue(server_root_fixture_name)

        def get_option(option_name):
            return request.config.getoption(option_name) or request.config.getini(option_name)

        host = host or get_option('nginx_host')
        port = port or get_option('nginx_port')
        if not port:
            port = get_random_port(port)
        nginx_exec = nginx_exec or get_option('nginx_exec')
        nginx_params = nginx_params or get_option('nginx_params')
        config_template = config_template or get_option('nginx_config_template')

        if not os.path.isdir(server_root):
            raise ValueError("Specified server root ('{}') is not an existing directory.".format(server_root))
        if config_template and not os.path.isfile(config_template):
            raise ValueError("Specified config template ('{}') is not an existing file.".format(config_template))

        tmpdir = tmpdir_factory.mktemp("nginx-data")

        extra_params = {"liveserver_host": str(live_server.thread.host),
                        "liveserver_port": str(live_server.thread.port)}
        if template_extra_params:
            extra_params.update(template_extra_params)

        config_path = init_nginx(tmpdir, config_template, host, port, server_root,
                                 template_str=template_str,
                                 template_extra_params=extra_params)

        cmd = "{} -c {} {}".format(nginx_exec, config_path, nginx_params)
        with daemon(cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    ) as proc:
            wait_for_socket_check_processes(host, port, [proc])
            yield NginxProcess(host, port, server_root)

    return nginx_proc_fixture


nginx_live_server = nginx_liveserver_proc()
