"""
Integration tests for the lightweight auth server.

Tests the is_superuser endpoint used by nginx auth_request
for protecting services like Grafana and Dozzle.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings
from django.urls import resolve


def test_auth_server_settings_import():
    """Verify auth_server settings module loads without errors."""
    from django_bpp.settings import auth_server

    assert auth_server.SECRET_KEY is not None
    assert auth_server.DATABASES is not None
    assert auth_server.AUTH_USER_MODEL == "bpp.BppUser"
    assert "bpp" in auth_server.INSTALLED_APPS


def test_is_superuser_unauthenticated_returns_unauthorized():
    """Unauthenticated requests should receive 401 Unauthorized."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = AnonymousUser()
    response = is_superuser(request)

    assert response.status_code == 401
    assert response.content == b"unauthorized"


@pytest.mark.django_db
def test_is_superuser_regular_user_gets_forbidden(test_user):
    """Non-superuser should receive 403 Forbidden."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = test_user
    response = is_superuser(request)

    assert response.status_code == 403
    assert response.content == b"forbidden"


@pytest.mark.django_db
def test_is_superuser_superuser_gets_ok_with_headers(superuser):
    """Superuser should receive 200 OK with user headers."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = superuser
    response = is_superuser(request)

    assert response.status_code == 200
    assert response.content == b"ok"
    assert response["X-WEBAUTH-USER"] == superuser.get_username()
    assert "X-WEBAUTH-EMAIL" in response
    assert "X-WEBAUTH-NAME" in response


@pytest.mark.django_db
def test_auth_server_health_endpoint_ok():
    """Healthy DB + Redis returns 200 with status ok."""
    import json

    from django_bpp.health import health_check

    rf = RequestFactory()
    request = rf.get("/health/")
    response = health_check(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


def test_health_check_returns_503_when_db_down(monkeypatch):
    """If DB ping fails, return 503 with the failing component."""
    import json

    from django_bpp import health

    # NIE patchujemy `health.connection.ensure_connection` — `connection` to
    # `ConnectionProxy` z `django.db`, którego `__setattr__` przekierowuje
    # zapis na realny `DatabaseWrapper` w `connections[default]`. Pytest
    # ``monkeypatch`` przy teardownie odtwarza „starą" wartość pobraną
    # przez ``getattr`` przez proxy — w teście bez ``@django_db`` to bound
    # ``pytest_django._blocking_wrapper``. ``setattr`` na proxy wstrzykuje
    # ten bound wrapper do ``connections[default].__dict__``, co nadpisuje
    # class-level patch i czyni ``django_db_blocker.unblock()``
    # nieskutecznym dla kolejnych testów na tym workerze (instance attr
    # ma priorytet) — pierwszy następny test używający DB pada na
    # ``RuntimeError: Database access not allowed`` w ``setup_databases``.
    # Patchujemy funkcję wyższego poziomu ``_check_db`` (symetrycznie do
    # ``test_health_check_returns_503_when_redis_down``).
    monkeypatch.setattr(health, "_check_db", lambda: "db: RuntimeError")
    monkeypatch.setattr(health, "_check_redis", lambda: None)

    rf = RequestFactory()
    response = health.health_check(rf.get("/health/"))

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body["status"] == "error"
    assert any("db" in f for f in body["failures"])


def test_health_check_returns_503_when_redis_down(monkeypatch):
    """If Redis ping fails, return 503 with the failing component."""
    import json

    from django_bpp import health

    monkeypatch.setattr(health, "_check_db", lambda: None)
    monkeypatch.setattr(health, "_check_redis", lambda: "redis: ConnectionError")

    rf = RequestFactory()
    response = health.health_check(rf.get("/health/"))

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body["status"] == "error"
    assert any("redis" in f for f in body["failures"])


def test_check_redis_skipped_without_broker_url():
    """Without CELERY_BROKER_URL (e.g. authserver settings), Redis check is
    skipped — returning None — instead of raising AttributeError.

    Regression test for: ``healthcheck: redis failed: AttributeError(
    "'Settings' object has no attribute 'CELERY_BROKER_URL'")``
    on the lightweight authserver.
    """
    from django.test.utils import override_settings

    from django_bpp import health

    # `override_settings(CELERY_BROKER_URL=None)` keeps the attribute defined
    # on the wrapper but maps it to None — exercises the falsy-value path.
    with override_settings(CELERY_BROKER_URL=None):
        assert health._check_redis() is None


def test_health_check_log_filter():
    """Test that UvicornHealthCheckFilter suppresses /health/ logs."""
    import logging

    from django_bpp.health import UvicornHealthCheckFilter

    f = UvicornHealthCheckFilter()

    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /health/ HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is False

    record_normal = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /api/v1/data HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    assert f.filter(record_normal) is True


def test_auth_server_installs_formdefaults_for_eager_templatetag_import():
    """formdefaults musi być w INSTALLED_APPS authservera.

    Django przy inicjalizacji silnika szablonów ładuje ZACHŁANNIE wszystkie
    moduły ``templatetags/*.py`` każdej aplikacji z INSTALLED_APPS — niezależnie
    od tego, czy renderowany szablon ich używa. Ponieważ ``bpp`` jest w
    INSTALLED_APPS authservera, importowany jest też ``bpp.templatetags.
    bpp_formdefaults``, który na top-levelu robi ``from formdefaults.models
    import FormRepresentation``. Bez ``formdefaults`` w INSTALLED_APPS ten model
    nie da się zdefiniować i samo wyrenderowanie formularza logowania
    authservera wywala się 500-tką.

    Regression test for: RuntimeError: Model class
    formdefaults.models.FormRepresentation doesn't declare an explicit
    app_label and isn't in an application in INSTALLED_APPS — przy
    GET /__external_auth/login/ na authserverze (Grafana/Dozzle redirect).
    """
    from django_bpp.settings import auth_server

    assert "formdefaults" in auth_server.INSTALLED_APPS, (
        "auth_server musi mieć 'formdefaults' w INSTALLED_APPS, bo "
        "bpp/templatetags/bpp_formdefaults.py importuje formdefaults.models "
        "na top-levelu, a Django importuje wszystkie templatetagi 'bpp' "
        "zachłannie przy starcie silnika szablonów."
    )


@pytest.mark.django_db
def test_auth_server_renders_login_template():
    """Formularz logowania authservera musi się wyrenderować bez wyjątku.

    Wymusza dokładnie ścieżkę, która padała w produkcji: inicjalizacja silnika
    szablonów (która importuje wszystkie templatetagi z INSTALLED_APPS) +
    rozwiązanie i renderowanie ``auth_server/login.html``. Test biegnie pod
    testowym settingsem, ale ``bpp`` + ``formdefaults`` są tam obecne tak samo
    jak na authserverze, więc waliduje, że łańcuch importów templatetagów 'bpp'
    nie wybucha.
    """
    from django.template.loader import get_template

    template = get_template("auth_server/login.html")
    # Pusty kontekst wystarcza — chodzi o to, że resolve + import templatetagów
    # nie rzuca RuntimeError (model bez app_label).
    assert template.render({}) is not None


def test_auth_server_startuje_i_renderuje_login_w_osobnym_procesie():
    """``django.setup()`` + render loginu pod PRAWDZIWYMI settingsami authservera.

    Testy jednostkowe biegną pod ``settings.test``, gdzie INSTALLED_APPS jest
    pełne — więc żaden z nich nie wykryje, że ``bpp`` przestało się ładować w
    minimalnym środowisku authservera. Ten test odpala Django w OSOBNYM
    procesie z ``DJANGO_SETTINGS_MODULE=django_bpp.settings.auth_server``,
    czyli dokładnie tak, jak robi to gunicorn przez ``wsgi_auth_server.py``.

    Pokrywa dwie klasy regresji, które już wystąpiły w produkcji:

    1. ``BppConfig.ready()`` importujący model aplikacji spoza minimalnych
       INSTALLED_APPS (``favicon`` — worker gunicorna nie wstawał w ogóle).
    2. Top-levelowy import modelu w ``bpp/templatetags/*.py`` — Django przy
       inicjalizacji silnika szablonów ładuje ZACHŁANNIE wszystkie moduły
       templatetagów aplikacji z INSTALLED_APPS, więc taki import wywala
       render formularza logowania (``formdefaults``, ``favicon``).

    Obie objawiają się tym samym: ``RuntimeError: Model class X doesn't
    declare an explicit app_label and isn't in an application in
    INSTALLED_APPS``.

    Nie dotyka bazy ani Redisa — ``django.setup()`` i ``get_template()`` są
    czysto in-process, więc test nie potrzebuje testcontainerów.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]

    skrypt = (
        "import django; django.setup();"
        "from django.template.loader import get_template;"
        "get_template('auth_server/login.html').render({});"
        # `csrf_token` w kontekście: bez niego {% csrf_token %} tylko loguje
        # ostrzeżenie i renderuje pustkę — chcemy czysty stderr, żeby realny
        # błąd importu był widoczny w komunikacie asercji.
        "get_template('auth_server/forbidden.html').render({'csrf_token': 'x'});"
        "print('AUTHSERVER OK')"
    )

    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "django_bpp.settings.auth_server",
        # `production.py` odmawia startu na placeholderze; wartość jest
        # nieistotna, bo nic nie podpisujemy — ważne, żeby nie była pusta.
        "DJANGO_BPP_SECRET_KEY": "x" * 64,
        "DJANGO_BPP_REDIS_DB_CACHE": "1",
        # Bez tego `.env` dewelopera nadpisałby powyższe.
        "DJANGO_BPP_SKIP_DOTENV": "1",
    }

    wynik = subprocess.run(
        [sys.executable, "-c", skrypt],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert wynik.returncode == 0, (
        "Authserver nie wstaje pod własnymi (minimalnymi) settingsami.\n"
        "Najczęstsza przyczyna: kod 'bpp' importuje model aplikacji, której "
        "nie ma w auth_server.INSTALLED_APPS — w ready() albo na top-levelu "
        "modułu templatetagów.\n\n"
        f"STDOUT:\n{wynik.stdout}\n\nSTDERR:\n{wynik.stderr}"
    )
    assert "AUTHSERVER OK" in wynik.stdout


def test_szablon_logowania_nie_udaje_awarii():
    """Formularz authservera nie może twierdzić, że to logowanie awaryjne.

    Ta strona pokazuje się na CODZIENNEJ, poprawnej ścieżce: nginx odsyła tu
    każdego, kto wchodzi na /grafana/, /dozzle/, /flower/ albo /netdata/ bez
    ważnej sesji (``error_page 401 = @bpp_login`` w bpp-deploy). Nie ma tu
    żadnej awarii ani startu systemu — gdy główna aplikacja nie odpowiada,
    nginx serwuje ``maintenance.html``, a nie ten formularz. Napisy
    „Emergency Login" i „System w trakcie uruchamiania" były nieprawdziwe:
    straszyły administratora awarią, której nie ma, a w historii przeglądarki
    zostawiały wpis wyglądający jak awaryjne wejście na skróty.
    """
    from django.template.loader import get_template

    html = get_template("auth_server/login.html").render({})

    assert "Emergency" not in html
    assert "trakcie uruchamiania" not in html
    assert "Logowanie do BPP" in html
    assert "narzędzi administracyjnych" in html


def test_szablony_authservera_maja_polskie_znaki():
    """Szablony authservera piszą po polsku z diakrytykami.

    Plik jest serwowany jako UTF-8, więc „Nazwa uzytkownika" / „Haslo" nie
    wynikały z żadnego ograniczenia technicznego.
    """
    from django.template.loader import get_template

    login = get_template("auth_server/login.html").render({})

    assert "Nazwa użytkownika" in login
    assert "Hasło" in login
    assert "Bibliografia Publikacji Pracowników" in login
    assert "uzytkownik" not in login.lower()
    assert "haslo" not in login.lower()


@pytest.mark.django_db
def test_brak_uprawnien_zwraca_403_z_czytelnym_wyjasnieniem(test_user):
    """Zalogowany nie-superuser dostaje stronę z wyjaśnieniem, nie gołe 403.

    ``is_superuser`` zwraca nginksowi 403, a nginx do tej pory pokazywał
    własną, generyczną stronę błędu — bez informacji, że problem to za niskie
    uprawnienia konta, na które użytkownik jest właśnie zalogowany.
    """
    from importlib import import_module

    from django.conf import settings

    from django_bpp.views import brak_uprawnien

    rf = RequestFactory()
    request = rf.get("/__external_auth/forbidden/")
    request.user = test_user
    # Sesja: pod testowym settingsem lista context processorów jest pełniejsza
    # niż minimalna lista authservera i część z nich sięga po request.session.
    # W produkcji dostarcza ją SessionMiddleware.
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()

    response = brak_uprawnien(request)

    assert response.status_code == 403
    tresc = response.content.decode("utf-8")
    assert "administrator" in tresc.lower()
    # Strona musi powiedzieć, NA KTÓRE konto użytkownik jest zalogowany —
    # najczęstsza realna przyczyna to zalogowanie się kontem redaktora
    # zamiast administratora.
    assert test_user.username in tresc


def test_authserver_wystawia_endpointy_braku_uprawnien_i_wylogowania():
    """URL-e muszą być podpięte w urlconfie authservera, nie tylko istnieć.

    nginx robi wewnętrzne przekierowanie na ``/__external_auth/forbidden/``
    (``error_page 403``), więc literalna ścieżka jest częścią kontraktu
    z bpp-deploy.
    """
    from django.contrib.auth.views import LogoutView

    from django_bpp.views import brak_uprawnien

    urlconf = "django_bpp.urls_auth_server"

    assert (
        resolve("/__external_auth/forbidden/", urlconf=urlconf).func is brak_uprawnien
    )
    assert (
        resolve("/__external_auth/logout/", urlconf=urlconf).func.view_class
        is LogoutView
    )


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF="django_bpp.urls_auth_server",
    # Middleware TAKIE JAK NA AUTHSERVERZE. Pełna lista z settings.test zawiera
    # m.in. password_policies, które na każdym żądaniu robi
    # reverse("password_change") — a authserver takiego route'u nie ma i nigdy
    # nie miał (NoReverseMatch). Test ma sprawdzać authserver, nie hybrydę.
    MIDDLEWARE=[
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
    ],
)
def test_wylogowanie_z_authservera_konczy_sesje_i_wraca_na_logowanie(client, test_user):
    """Ze strony 403 da się wyjść: wylogować i wejść kontem administratora.

    Sesja jest współdzielona z główną aplikacją (ten sam SECRET_KEY, ten sam
    backend sesji w Redisie), więc wylogowanie tutaj kończy też sesję w BPP —
    dlatego szablon mówi o tym wprost.
    """
    client.force_login(test_user)

    # Django >= 5.0: wylogowanie tylko POST-em. GET nie może kończyć sesji,
    # bo prefetch linku przez przeglądarkę wylogowywałby użytkownika.
    assert client.get("/__external_auth/logout/").status_code == 405
    assert "_auth_user_id" in client.session

    response = client.post("/__external_auth/logout/")

    assert response.status_code == 302
    assert response["Location"] == "/__external_auth/login/"
    assert "_auth_user_id" not in client.session


def test_auth_server_has_rollbar_config():
    """
    Verify auth server settings include ROLLBAR configuration.

    The bpp app's ready() method calls configure_rollbar() which requires
    settings.ROLLBAR to exist. This test ensures the auth server settings
    include ROLLBAR to prevent AttributeError on startup.

    Regression test for: AttributeError: 'Settings' object has no attribute
    'ROLLBAR'
    """
    from django_bpp.settings import auth_server

    assert hasattr(auth_server, "ROLLBAR"), (
        "auth_server settings must include ROLLBAR configuration "
        "because bpp app is in INSTALLED_APPS and calls configure_rollbar()"
    )
    assert isinstance(auth_server.ROLLBAR, dict)
    assert "access_token" in auth_server.ROLLBAR
    assert "environment" in auth_server.ROLLBAR
