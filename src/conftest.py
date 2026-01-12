from datetime import timedelta
from uuid import uuid4

import pytest
from django.apps import apps
from django.contrib import auth
from django.test.client import Client, RequestFactory
from django.utils import timezone
from model_bakery import baker

from bpp.tests.helpers import (  # noqa: F401 - re-export helpers
    UserRequestFactory,
    _enrich_kw_for_wydawnictwo,
    _stworz_obiekty_dla_raportow,
    autor_ciaglego,
    autor_publikacji,
    autor_zwartego,
    ciagle_publikacja,
    zwarte_publikacja,
)
from channels_live_server import channels_live_server  # noqa: F401 pytest fixture

# =============================================================================
# Fixtures użytkowników i klientów (przeniesione z tests_legacy/conftest.py)
# =============================================================================

User = auth.get_user_model()

# Stałe dla fixtures
TEST_USERNAME = "user"
TEST_PASSWORD = "foo"
TEST_EMAIL = "foo@bar.pl"


@pytest.fixture
def web_client():
    """Fixture zwracający Client."""
    return Client()


@pytest.fixture
def request_factory():
    """Fixture zwracający RequestFactory."""
    return RequestFactory()


@pytest.fixture
def test_user(db):
    """Fixture tworzący zwykłego użytkownika."""
    return User.objects.create_user(
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        email=TEST_EMAIL,
    )


@pytest.fixture
def superuser(db):
    """Fixture tworzący superusera."""
    return User.objects.create_superuser(
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        email=TEST_EMAIL,
    )


@pytest.fixture
def logged_in_client(client, test_user):
    """Fixture zwracający zalogowany Client."""
    logged_in = client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
    if not logged_in:
        raise Exception("Cannot login")
    return client


@pytest.fixture
def superuser_client(client, superuser):
    """Fixture zwracający zalogowanego superusera."""
    logged_in = client.login(username=TEST_USERNAME, password=TEST_PASSWORD)
    if not logged_in:
        raise Exception("Cannot login")
    return client


@pytest.fixture
def user_request_factory(test_user):
    """Fixture zwracający UserRequestFactory."""
    return UserRequestFactory(test_user)


# =============================================================================
# Helpery do tworzenia publikacji (przeniesione do bpp.tests.helpers)
# =============================================================================


@pytest.fixture
def make_autor(db):
    """
    Fixture-factory do tworzenia autora z przypisaniem do jednostki.

    Użycie:
        def test_foo(make_autor, jednostka):
            autor = make_autor(jednostka)
    """
    from bpp.models import Autor_Jednostka, Funkcja_Autora
    from bpp.tests.util import any_autor

    def _make_autor(jednostka, **kw):
        a = any_autor()
        Autor_Jednostka.objects.create(
            autor=a, jednostka=jednostka, funkcja=baker.make(Funkcja_Autora), **kw
        )
        return a

    return _make_autor


@pytest.fixture
def make_ciagle(db):
    """
    Fixture-factory do tworzenia wydawnictwa ciągłego z autorem.

    Użycie:
        def test_foo(make_ciagle, autor, jednostka):
            ciagle = make_ciagle(autor, jednostka, tytul_oryginalny="Test")
    """
    from bpp.models import (
        Typ_Odpowiedzialnosci,
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
    )

    def _make_ciagle(autor, jednostka, **kw):
        _enrich_kw_for_wydawnictwo(kw)
        w = baker.make(Wydawnictwo_Ciagle, **kw)
        typ_odp = baker.make(Typ_Odpowiedzialnosci)
        Wydawnictwo_Ciagle_Autor.objects.create(
            autor=autor,
            rekord=w,
            jednostka=jednostka,
            typ_odpowiedzialnosci=typ_odp,
            zapisany_jako=f"{autor.nazwisko} {autor.imiona[0]}",
        )
        return w

    return _make_ciagle


@pytest.fixture
def make_zwarte(db):
    """
    Fixture-factory do tworzenia wydawnictwa zwartego z autorem.

    Użycie:
        def test_foo(make_zwarte, autor, jednostka, typ_odpowiedzialnosci):
            zwarte = make_zwarte(autor, jednostka, typ_odpowiedzialnosci)
    """
    from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor

    def _make_zwarte(autor, jednostka, typ_odpowiedzialnosci, **kw):
        _enrich_kw_for_wydawnictwo(kw)
        z = baker.make(Wydawnictwo_Zwarte, **kw)
        Wydawnictwo_Zwarte_Autor.objects.create(
            autor=autor,
            rekord=z,
            jednostka=jednostka,
            typ_odpowiedzialnosci=typ_odpowiedzialnosci,
            zapisany_jako=f"{autor.nazwisko} {autor.imiona[0]}",
        )
        return z

    return _make_zwarte


@pytest.fixture
def stworz_obiekty_dla_raportow(db):
    """
    Fixture tworzący standardowe obiekty potrzebne do raportów.
    """
    _stworz_obiekty_dla_raportow()


# Aliasy dla kompatybilności wstecznej z test_reports/util.py
# (funkcje zaimportowane z bpp.tests.helpers)
stworz_obiekty_dla_raportow_func = _stworz_obiekty_dla_raportow
autor = autor_publikacji
ciagle = ciagle_publikacja
zwarte = zwarte_publikacja

# Fix for VCR.py compatibility with urllib3
# This resolves the AttributeError: 'VCRHTTPConnection' has no attribute 'debuglevel'


def pytest_configure(config):  # noqa
    try:
        import http.client

        import vcr

        # Patch VCR's HTTP connection classes to include required attributes
        original_vcr_stubs_init = (
            vcr.stubs.VCRHTTPConnection.__init__ if hasattr(vcr, "stubs") else None
        )

        def patched_init(self, *args, **kwargs):
            # Set default debuglevel before calling original init
            self.debuglevel = getattr(http.client.HTTPConnection, "debuglevel", 0)
            if original_vcr_stubs_init:
                original_vcr_stubs_init(self, *args, **kwargs)

        if hasattr(vcr, "stubs"):
            vcr.stubs.VCRHTTPConnection.__init__ = patched_init
            vcr.stubs.VCRHTTPSConnection.__init__ = patched_init

            # Ensure the class has all required attributes from http.client
            if not hasattr(vcr.stubs.VCRHTTPConnection, "debuglevel"):
                vcr.stubs.VCRHTTPConnection.debuglevel = 0
            if not hasattr(vcr.stubs.VCRHTTPSConnection, "debuglevel"):
                vcr.stubs.VCRHTTPSConnection.debuglevel = 0

            # Add _http_vsn and _http_vsn_str attributes required by urllib3
            if not hasattr(vcr.stubs.VCRHTTPConnection, "_http_vsn"):
                vcr.stubs.VCRHTTPConnection._http_vsn = 11
            if not hasattr(vcr.stubs.VCRHTTPConnection, "_http_vsn_str"):
                vcr.stubs.VCRHTTPConnection._http_vsn_str = "HTTP/1.1"
            if not hasattr(vcr.stubs.VCRHTTPSConnection, "_http_vsn"):
                vcr.stubs.VCRHTTPSConnection._http_vsn = 11
            if not hasattr(vcr.stubs.VCRHTTPSConnection, "_http_vsn_str"):
                vcr.stubs.VCRHTTPSConnection._http_vsn_str = "HTTP/1.1"

            # Add version_string property to VCRHTTPResponse for urllib3 2.5.0+ compatibility
            if hasattr(vcr.stubs, "VCRHTTPResponse"):
                if not hasattr(vcr.stubs.VCRHTTPResponse, "version_string"):
                    # Create a property that returns HTTP/1.1 as the version string
                    def _get_version_string(self):
                        # Return HTTP/1.1 as a sensible default
                        # This matches the _http_vsn_str we set above
                        return "HTTP/1.1"

                    vcr.stubs.VCRHTTPResponse.version_string = property(
                        _get_version_string
                    )

    except ImportError:
        # VCR not installed, skip configuration
        pass


def pytest_collection_modifyitems(items):
    """Ensure tests marked with 'serial' run sequentially on the same worker in pytest-xdist."""
    for item in items:
        if "serial" in item.keywords:
            # Assign all serial tests to the same xdist_group so they run on the same worker
            item.add_marker(pytest.mark.xdist_group("serial"))


pytest.mark.uruchom_tylko_bez_microsoft_auth = pytest.mark.skipif(
    apps.is_installed("microsoft_auth"),
    reason="działa wyłącznie bez django_microsoft_auth. Ta "
    "funkcja prawdopodobnie potrzebuje zalogowac do systemu zwykłego "
    "użytkownika i nie potrzebuje autoryzacji do niczego więcej. "
    "Możesz ją spokojnie przetestować z wyłączonym modułem microsoft_auth",
)

pytest.mark.uruchom_tylko_z_microsoft_auth = pytest.mark.skipif(
    not apps.is_installed("microsoft_auth"),
    reason="działa wyłącznie z zainstalowanym django_microsoft_auth",
)


@pytest.fixture
def pbn_dyscyplina2(db, pbn_discipline_group):
    from pbn_api.models import Discipline

    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        uuid=uuid4(),
        code="202",
        name="druga dyscyplina",
        scientificFieldName="Dziedzina drugich dyscyplin",
    )[0]


@pytest.fixture
def pbn_discipline_group(db):
    from pbn_api.models import DisciplineGroup

    n = timezone.now().date()
    try:
        return DisciplineGroup.objects.get_or_create(
            validityDateTo=None,
            validityDateFrom=n - timedelta(days=7),
            defaults=dict(uuid=uuid4()),
        )[0]
    except DisciplineGroup.MultipleObjectsReturned:
        return DisciplineGroup.objects.filter(
            validityDateTo=None,
            validityDateFrom=n - timedelta(days=7),
        ).first()


@pytest.fixture
def pbn_dyscyplina1(db, pbn_discipline_group):
    from pbn_api.models import Discipline

    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        code="301",
        name="memetyka stosowana",
        scientificFieldName="Dziedzina memetyk",
        defaults=dict(uuid=uuid4()),
    )[0]


@pytest.fixture
@pytest.mark.django_db
def zwarte_z_dyscyplinami(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    charaktery_formalne,
    wydawca,
    typy_odpowiedzialnosci,
    rok,
    rodzaj_autora_n,
):
    from model_bakery import baker

    from bpp.models import Autor_Dyscyplina, Charakter_Formalny

    # Żeby eksportować oświadczenia, autor musi mieć swój odpowiednik w PBNie:
    autor_jan_nowak.pbn_uid = baker.make("pbn_api.Scientist")
    autor_jan_nowak.save()

    autor_jan_kowalski.pbn_uid = baker.make("pbn_api.Scientist")
    autor_jan_kowalski.save()

    # Musi miec też przypisania do dyscyplin
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        dyscyplina_naukowa=dyscyplina1,
        rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina2,
        rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    # domyslnie: ksiazka/autorstwo/wydawca spoza wykazu
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.save()

    wydawnictwo_zwarte.przelicz_punkty_dyscyplin()

    return wydawnictwo_zwarte


def _dyscyplina_maker(nazwa, kod, dyscyplina_pbn):
    """Produkuje dyscypliny naukowe WRAZ z odpowiednim wpisem tłumacza
    dyscyplin"""
    from bpp.models import Dyscyplina_Naukowa
    from pbn_api.models import TlumaczDyscyplin

    d = Dyscyplina_Naukowa.objects.get_or_create(nazwa=nazwa, kod=kod)[0]
    TlumaczDyscyplin.objects.get_or_create(
        dyscyplina_w_bpp=d,
        pbn_2017_2021=dyscyplina_pbn,
        pbn_2022_2023=dyscyplina_pbn,
        pbn_2024_now=dyscyplina_pbn,
    )
    return d


@pytest.fixture
def dyscyplina1(db, pbn_dyscyplina1):
    return _dyscyplina_maker(
        nazwa="memetyka stosowana", kod="3.1", dyscyplina_pbn=pbn_dyscyplina1
    )


@pytest.fixture
def dyscyplina1_hst(db, pbn_dyscyplina1_hst):
    return _dyscyplina_maker(
        nazwa="nauka teologiczna", kod="7.1", dyscyplina_pbn=pbn_dyscyplina1_hst
    )


@pytest.fixture
def dyscyplina2(db, pbn_dyscyplina2):
    return _dyscyplina_maker(
        nazwa="druga dyscyplina", kod="2.2", dyscyplina_pbn=pbn_dyscyplina2
    )


# Import Playwright fixtures
from fixtures.playwright_fixtures import (  # noqa
    admin_page,
    preauth_asgi_page,
    preauth_page,
)


@pytest.fixture
def rodzaj_autora_n(db):
    """Fixture dla rodzaju autora N (pracownik naukowy w liczbie N)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults=dict(
            nazwa="pracownik naukowy w liczbie N",
            jest_w_n=True,
            licz_sloty=True,
            sort=1,
        ),
    )
    return obj


@pytest.fixture
def rodzaj_autora_d(db):
    """Fixture dla rodzaju autora D (doktorant)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="D",
        defaults=dict(nazwa="doktorant", jest_w_n=False, licz_sloty=True, sort=3),
    )
    return obj


@pytest.fixture
def rodzaj_autora_b(db):
    """Fixture dla rodzaju autora B (pracownik badawczy spoza N)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="B",
        defaults=dict(
            nazwa="pracownik badawczy spoza N",
            jest_w_n=False,
            licz_sloty=True,
            sort=2,
        ),
    )
    return obj


@pytest.fixture
def rodzaj_autora_z(db):
    """Fixture dla rodzaju autora Z (inny zatrudniony, nie naukowy)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="Z",
        defaults=dict(
            nazwa="inny zatrudniony, nie naukowy",
            jest_w_n=False,
            licz_sloty=False,
            sort=4,
        ),
    )
    return obj


@pytest.fixture
def constance_cache_warmed_up(db):
    """
    Fixture that pre-creates constance values in the database and warms
    the cache to prevent constance queries during test execution.

    This ensures all constance values exist in the DB before the test runs,
    avoiding INSERT/UPDATE queries during the test's query assertion block.
    """
    import json

    from constance import config
    from constance.models import Constance
    from django.conf import settings

    # Create all constance values in the database if they don't exist
    for key, (default, _help_text, _value_type) in settings.CONSTANCE_CONFIG.items():
        # Format value as constance expects it (JSON with __type__ and __value__)
        value_json = json.dumps({"__type__": "default", "__value__": default})
        Constance.objects.get_or_create(key=key, defaults={"value": value_json})

    # Warm the cache by accessing all values
    _ = (
        config.UZYWAJ_PUNKTACJI_WEWNETRZNEJ,
        config.POKAZUJ_INDEX_COPERNICUS,
        config.POKAZUJ_PUNKTACJA_SNIP,
        config.POKAZUJ_OSWIADCZENIE_KEN,
        config.SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI,
        config.UCZELNIA_UZYWA_WYDZIALOW,
        config.GOOGLE_ANALYTICS_PROPERTY_ID,
        config.GOOGLE_VERIFICATION_CODE,
    )
    return config
