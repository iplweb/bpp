import random
import time
from datetime import date
from uuid import uuid4

import pytest
from django.apps import apps
from django.contrib import auth
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.db.utils import OperationalError
from django.test import TransactionTestCase
from django.test.client import Client, RequestFactory
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
from channels_live_server import (  # noqa: F401
    channels_live_server,
    channels_live_server_per_test,
)

# pytest_plugins: rejestrujemy fixture'owe moduły jako pluginy, żeby
# pytest zastosował assert-rewriting zanim je zaimportuje. Bez tej
# deklaracji było 85+ ostrzeżeń ``PytestAssertRewriteWarning: Module
# already imported so cannot be rewritten; fixtures.conftest_*``.
# Kolejność wewnątrz conftest nie ma znaczenia — pytest czyta atrybut
# po pełnym załadowaniu modułu; ważne, żeby
# ``fixtures/__init__.py`` NIE importował tych modułów eager
# (`from .conftest_X import *`), inaczej trafiają do ``sys.modules``
# przed rejestracją.
#
# UWAGA: ``fixtures.conftest`` NIE może być na tej liście — to plik
# ``conftest.py``, który pytest auto-rejestruje pod nazwą pełnej
# ścieżki. Dodanie go tu powoduje ``ValueError: Plugin already
# registered under a different name`` przy collectowaniu.
pytest_plugins = [
    "fixtures.conftest_models",
    "fixtures.conftest_publications",
    "fixtures.conftest_system",
    "fixtures.conftest_browser",
    "fixtures.conftest_disciplines",
    # ``conftest_multisite`` importuje modele Django na top-levelu (``Site``,
    # ``Uczelnia``, ``BppUser``...), więc — jak moduły niżej — MUSI być tutaj.
    # Rejestracja wyłącznie w rootdir-owym ``conftest.py`` nie wystarcza: jego
    # ``pytest_plugins`` ładuje się w preloadzie ``pytest-testcontainers-django``
    # ZANIM ``django.setup()`` zapełni rejestr aplikacji, import wybucha
    # ``AppRegistryNotReady`` i fikstury (``site1``, ``uczelnia1``...) cicho się
    # nie rejestrują → ``fixture 'site1' not found``. Guard:
    # bpp/tests/test_conftest_preload_safety.py.
    "fixtures.conftest_multisite",
    # ``pbn_api`` i ``wydawnictwa`` importują modele Django na top-levelu,
    # więc MUSZĄ być rejestrowane tutaj (plugin ładowany po ``django.setup()``),
    # a NIE przez ``from fixtures import *`` w rootdir-owym ``conftest.py`` —
    # ten jest preloadowany ZANIM apps Django są ready i wybucha
    # ``AppRegistryNotReady``. Guard: bpp/tests/test_conftest_preload_safety.py.
    "fixtures.pbn_api",
    "fixtures.wydawnictwa",
]

# Baseline test-DB monkey-patch is installed by
# ``django_pg_baseline.apps.DjangoPgBaselineConfig.ready()`` z zewnetrznego
# pakietu ``django-pg-baseline`` (PyPI). INSTALLED_APPS zawiera
# "django_pg_baseline" + settings.PG_BASELINE konfiguruje BASELINE_DIR.


# =============================================================================
# Monkey-patch TransactionTestCase._fixture_teardown to allow TRUNCATE CASCADE.
#
# Niezarządzane przez Django tabele (np. ``bpp_rekord_mat``, ``bpp_autorzy_mat``)
# mają realne FK do tabel zarządzanych (``bpp_charakter_formalny`` itd.) — bez
# CASCADE Django flush() crashuje na ``cannot truncate a table referenced in a
# foreign key constraint``. Poza tym przy równoległym xdist okazjonalnie łapiemy
# deadlock-i, więc dorzucamy retry z exponential backoff.
#
# Patch MUSI siedzieć w ``src/conftest.py`` (auto-loadowane dla wszystkich
# testów w ``testpaths=src``); ``src/fixtures/conftest.py`` jest siostrzanym
# katalogiem i pytest go NIE ładuje dla testów spoza ``src/fixtures/``.
# =============================================================================


def _fixture_teardown(self):
    # Allow TRUNCATE ... CASCADE and don't emit the post_migrate signal
    # when flushing only a subset of the apps
    for db_name in self._databases_names(include_mirrors=False):
        # Flush the database
        inhibit_post_migrate = self.available_apps is not None or (
            # Inhibit the post_migrate signal when using serialized rollback
            # to avoid trying to recreate the serialized data.
            self.serialized_rollback
            and hasattr(connections[db_name], "_test_serialized_contents")
        )

        # Add retry logic for deadlock handling
        max_retries = 5
        for attempt in range(max_retries):
            try:
                call_command(
                    "flush",
                    verbosity=0,
                    interactive=False,
                    database=db_name,
                    reset_sequences=False,
                    # In the real TransactionTestCase this is conditionally set to False.
                    allow_cascade=True,
                    inhibit_post_migrate=inhibit_post_migrate,
                )
                break  # Success, exit retry loop
            except (OperationalError, CommandError) as e:
                # Check for deadlock in both the exception and its cause
                error_msg = str(e).lower()
                is_deadlock = (
                    "deadlock detected" in error_msg or "zakleszczenie" in error_msg
                )

                # Also check the chained exception (CommandError wraps OperationalError)
                if not is_deadlock and hasattr(e, "__cause__") and e.__cause__:
                    cause_msg = str(e.__cause__).lower()
                    is_deadlock = (
                        "deadlock detected" in cause_msg or "zakleszczenie" in cause_msg
                    )

                if is_deadlock and attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    base_delay = 0.5 * (2**attempt)
                    jitter = random.uniform(0, base_delay)
                    time.sleep(base_delay + jitter)
                    continue
                else:
                    # Re-raise if not a deadlock or max retries exceeded
                    raise


TransactionTestCase._fixture_teardown = _fixture_teardown


# =============================================================================
# Izolacja pod xdist: neutralizacja WYCIEKŁYCH scommitowanych danych domenowych.
#
# Problem (CI, sharding pytest-split + xdist -n auto): pod obciążeniem CI test,
# który commituje dane poza rollback (transakcyjny / live-server / komenda z
# własnym commitem), potrafi zostawić w bazie workera scommitowane wiersze
# autorów/jednostek/stopni/stanowisk. Kolejne testy na tym samym workerze widzą
# ambient dane → ``IntegrityError: bpp_jednostka_nazwa_key``,
# ``bpp_stopiensluzbowy_nazwa_key``, albo asercje typu „pusta baza zwraca []"
# pękają. Flake jest niezawodny na CI, ale niereprodukowalny lokalnie
# (testcontainers, nawet -n 8) — dlatego bronimy się defensywnie, a nie przez
# szukanie pojedynczego winowajcy.
#
# Baseline testowy ma 0 wierszy w tych tabelach (zweryfikowane), więc TRUNCATE
# przed testem = przywrócenie stanu baseline (NIE rusza danych referencyjnych —
# ``bpp_tytul``/``bpp_funkcja_autora``/… mają dane i NIE są tu wymienione).
# CASCADE jest bezpieczny: żadna NIEPUSTA (referencyjna) tabela nie ma FK DO
# tych tabel (zweryfikowane zapytaniem po information_schema), więc kaskada
# zostaje w obrębie danych domenowych. Osobne autocommit-połączenie czyści
# COMMITTED wiersze (poza transakcją testu). Leak-triggered: TRUNCATE odpala
# się tylko gdy wykryty wyciek, więc w normalnym przypadku to 1 tani probe.
#
# DIAGNOSTYKA: przy wykryciu wycieku guard wypisuje do stderr (widoczne w
# logach CI) które tabele wyciekły oraz najprawdopodobniejszego SPRAWCĘ —
# poprzedni test DB na tym workerze. Bo guard sprawdza każdy test DB i czyści
# przy każdym wykryciu, więc wyciek widziany na setupie testu X powstał po
# ostatnim czystym stanie = w poprzednim teście DB. To ścieżka do docelowego
# root-cause fixa (namierzyć i naprawić test commitujący poza rollback).
# =============================================================================

_LEAK_GUARD = {"conn": None, "poprzedni": "<start sesji>", "ref_snapshot": None}
_LEAK_GUARD_TABLES = (
    "bpp_autor",
    "bpp_jednostka",
    "bpp_stopiensluzbowy",
    "bpp_stanowiskodydaktyczne",
    "bpp_grupa_pracownicza",
)
# Sentinel dla WYCIEKU odwrotnego (vector 2): tabela referencyjna zaseedowana
# migracją danych, której post_migrate NIE odtwarza po flushu. Gdy jest pusta,
# a snapshot ją miał → transakcyjny flush zmiótł dane referencyjne workera.
_LEAK_GUARD_SENTINEL = "bpp_crossref_mapper"


def _snapshot_reference(cur):
    """Snapshot tabel referencyjnych (niepuste w świeżym baseline) do schematu
    ``_bp_snap``. Pomijamy tabele Django/auth (post_migrate je odtwarza) oraz
    tabele domenowe z guarda (puste w baseline). UNLOGGED = szybko, przeżywa
    flush (nie jest tabelą modelu → Django flush jej nie truncatuje)."""
    cur.execute("CREATE SCHEMA IF NOT EXISTS _bp_snap")
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    tabele = [r[0] for r in cur.fetchall()]
    ref = []
    for t in tabele:
        if t in _LEAK_GUARD_TABLES or t.startswith(
            ("django_", "auth_", "social_", "_bp_snap")
        ):
            continue
        cur.execute(f'SELECT EXISTS(SELECT 1 FROM "{t}")')
        if cur.fetchone()[0]:
            cur.execute(f'DROP TABLE IF EXISTS _bp_snap."{t}"')
            cur.execute(f'CREATE UNLOGGED TABLE _bp_snap."{t}" AS TABLE "{t}"')
            ref.append(t)
    return ref


def _restore_reference(cur, ref):
    """Przywróć dane referencyjne ze snapshotu. ``session_replication_role =
    replica`` wyłącza triggery FK → DELETE+INSERT w dowolnej kolejności (dane
    są spójnym baseline, brak realnych naruszeń)."""
    cur.execute("SET session_replication_role = replica")
    try:
        for t in ref:
            cur.execute(f'DELETE FROM "{t}"')
            cur.execute(f'INSERT INTO "{t}" SELECT * FROM _bp_snap."{t}"')
    finally:
        cur.execute("SET session_replication_role = origin")


def _leak_guard_conn(settings_dict):
    import psycopg2

    conn = _LEAK_GUARD["conn"]
    if conn is not None and not conn.closed:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except psycopg2.Error:
            try:
                conn.close()
            except psycopg2.Error:
                pass
            _LEAK_GUARD["conn"] = None
    conn = psycopg2.connect(
        dbname=settings_dict["NAME"],
        user=settings_dict.get("USER") or None,
        password=settings_dict.get("PASSWORD") or None,
        host=settings_dict.get("HOST") or None,
        port=settings_dict.get("PORT") or None,
    )
    conn.autocommit = True
    _LEAK_GUARD["conn"] = conn
    return conn


@pytest.fixture(autouse=True)
def _neutralizuj_wyciekle_dane(request):
    """Przed testem DB czyści ambient (scommitowane poza rollback) dane domenowe.

    Patrz komentarz nad definicją ``_LEAK_GUARD_TABLES``. No-op dla testów bez
    bazy i gdy nic nie wyciekło.
    """
    uzywa_db = (
        request.node.get_closest_marker("django_db") is not None
        or "db" in request.fixturenames
        or "transactional_db" in request.fixturenames
    )
    if uzywa_db:
        import sys

        import psycopg2
        from django.db import connection

        # Per-tabela (nie jeden OR) — żeby w raporcie nazwać CO wyciekło.
        probe = ", ".join(f"EXISTS(SELECT 1 FROM {t})" for t in _LEAK_GUARD_TABLES)
        try:
            conn = _leak_guard_conn(connection.settings_dict)
            with conn.cursor() as cur:
                # --- Snapshot referencyjny raz per worker (na świeżym baseline) ---
                if _LEAK_GUARD["ref_snapshot"] is None:
                    cur.execute(f"SELECT EXISTS(SELECT 1 FROM {_LEAK_GUARD_SENTINEL})")
                    if cur.fetchone()[0]:
                        _LEAK_GUARD["ref_snapshot"] = _snapshot_reference(cur)

                # --- VECTOR 2: przywróć dane referencyjne zmiecione flushem ---
                ref = _LEAK_GUARD["ref_snapshot"]
                if ref:
                    cur.execute(f"SELECT EXISTS(SELECT 1 FROM {_LEAK_GUARD_SENTINEL})")
                    if not cur.fetchone()[0]:
                        print(
                            f"[LEAK-GUARD] dane referencyjne WYCZYSZCZONE (flush "
                            f"transakcyjny) — widać na setupie {request.node.nodeid}. "
                            f"Sprawca (poprzedni test DB na tym workerze): "
                            f"{_LEAK_GUARD['poprzedni']}. Odtwarzam ze snapshotu.",
                            file=sys.stderr,
                        )
                        _restore_reference(cur, ref)

                # --- VECTOR 1: usuń wyciekłe (nadmiarowe) dane domenowe ---
                cur.execute(f"SELECT {probe}")
                obecne = cur.fetchone()
                wyciekle = [
                    t
                    for t, jest in zip(_LEAK_GUARD_TABLES, obecne, strict=False)
                    if jest
                ]
                if wyciekle:
                    # Guard sprawdza KAŻDY test DB i czyści przy każdym wykryciu,
                    # więc wyciek widziany na setupie tego testu powstał po
                    # ostatnim czystym stanie — sprawcą jest poprzedni test DB
                    # na tym workerze (xdist → proces = worker, stan per-proces).
                    print(
                        f"[LEAK-GUARD] wyciek scommitowanych danych na setupie "
                        f"{request.node.nodeid}: {', '.join(wyciekle)}. "
                        f"Najprawdopodobniejszy sprawca (poprzedni test DB na tym "
                        f"workerze): {_LEAK_GUARD['poprzedni']}",
                        file=sys.stderr,
                    )
                    # Bez RESTART IDENTITY — jak flush (_fixture_teardown używa
                    # reset_sequences=False); sekwencje rosną dalej, brak
                    # niespodzianek z pk=1.
                    cur.execute(
                        "TRUNCATE " + ", ".join(_LEAK_GUARD_TABLES) + " CASCADE"
                    )
            _LEAK_GUARD["poprzedni"] = request.node.nodeid
        except psycopg2.Error:
            # Guard jest best-effort: brak połączenia / brak tabel (np. test
            # bez pełnej migracji) nie może wywalić samego testu.
            pass
    yield


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

            # vcrpy >=8.1.1 sets self.version_string = None in VCRHTTPResponse.__init__,
            # so we no longer add a read-only property here (would break instance assignment).

    except ImportError:
        # VCR not installed, skip configuration
        pass


def pytest_collection_modifyitems(items):
    """Ensure tests marked with 'serial' run sequentially on the same worker in pytest-xdist."""
    for item in items:
        if "serial" in item.keywords:
            # Group serial tests by directory prefix (4 path components) so that
            # playwright/integration/multiseek/pbn groups each land on a separate
            # worker instead of all queuing on one. Tests within a group still run
            # sequentially because xdist_group guarantees same-worker ordering.
            path_parts = item.nodeid.split("/")
            group_key = "_".join(path_parts[: min(4, len(path_parts) - 1)])
            item.add_marker(pytest.mark.xdist_group(f"serial_{group_key}"))


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
        code="202",
        name="druga dyscyplina",
        scientificFieldName="Dziedzina drugich dyscyplin",
        defaults=dict(uuid=uuid4()),
    )[0]


@pytest.fixture
def pbn_discipline_group(db):
    from pbn_api.models import DisciplineGroup

    # Stały klucz naturalny (nie data bieżąca): leftover z sesji rozpoczętej
    # wczoraj (reuse-db + crash teardown) nadal matchuje, więc nie powstaje
    # drugi słownik. Data w przeszłości + validityDateTo=None => słownik jest
    # ciągle „aktualny" wg DisciplineGroupManager.get_current (validityDateFrom
    # <= dziś oraz validityDateTo IS NULL).
    stala_data_od = date(2020, 1, 1)
    try:
        return DisciplineGroup.objects.get_or_create(
            validityDateTo=None,
            validityDateFrom=stala_data_od,
            defaults=dict(uuid=uuid4()),
        )[0]
    except DisciplineGroup.MultipleObjectsReturned:
        return (
            DisciplineGroup.objects.filter(
                validityDateTo=None,
                validityDateFrom=stala_data_od,
            )
            .order_by("pk")
            .first()
        )


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
    admin_page_per_test,
    preauth_asgi_page,
    preauth_asgi_page_per_test,
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

    Note: Most constance settings have been migrated to Uczelnia model fields.
    This fixture now only handles remaining constance entries (if any).
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

    return config


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Rebuild denorm triggers on the freshly-built test DB, then jitter
    sequences.

    MUSI być w top-level conftest (nie w ``src/fixtures/conftest.py``, który
    auto-loaduje się tylko dla testów w ``src/fixtures/``) — inaczej triggery
    denorm dla większości testów pochodzą prosto z ``baseline.sql`` i nikt ich
    nie odświeża.

    drop_triggers() PRZED install_triggers() — pełny rebuild, nie tylko
    CREATE OR REPLACE istniejących. Baseline.sql niesie osierocone triggery
    z denorm 1.11.x (np. ``d_aft_row_upd_on_bpp_wydawnictwo_ciagle``,
    2-kolumnowy INSERT z ZASZYTYM content_type_id), których 1.12.0 nie
    nadpisuje, bo self-update trigger zmienił nazwę na ``..._<func>_self``.
    Taki sierota wstawia stałe content_type_id, a w testach (transakcyjny
    flush + ``post_migrate``) ID typów treści dryfują → ForeignKeyViolation na
    ``denorm_dirtyinstance``. drop_triggers() (po fixie wzorca nazw w denorm
    1.12.1) usuwa wszystkie ``d_*``-triggery, a install_triggers() instaluje
    świeże, rozwiązujące content_type dynamicznie (patrz
    ``denorm.helpers.content_type_select_sql``).
    """
    from denorm import denorms
    from django.db import connection

    with django_db_blocker.unblock():
        denorms.drop_triggers()
        denorms.install_triggers()

        # Przesuń każdą sekwencję w public o losową wartość z zakresu
        # [50 000, 500 000], niezależnie per sekwencja. Cel: nie pozwolić
        # testom dostawać 1-/2-cyfrowych ID, które maskują bugi zależne od
        # szerokości ID (padding, długość slugów, przekroczenia granicy cyfr).
        # Różne offsety per tabela dodatkowo rozsynchronizowują relacje między
        # ID różnych tabel, co demaskuje testy zakładające np.
        # autor.pk == jednostka.pk. Ziarno PRNG: ``random`` jest seedowane
        # przez pytest-randomly (jeśli zainstalowane) albo systemowo.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT schemaname, sequencename FROM pg_sequences "
                "WHERE schemaname = 'public'"
            )
            sequences = cursor.fetchall()
            if sequences:
                # Jedna kwerenda UNION ALL pobiera last_value + is_called ze
                # wszystkich sekwencji jednym round-tripem; wszystkie ALTER-y
                # idą jednym multi-statement batchem.
                values_sql = " UNION ALL ".join(
                    f"SELECT '{name}' AS sn, last_value, is_called "
                    f'FROM "{schema}"."{name}"'
                    for schema, name in sequences
                )
                cursor.execute(values_sql)
                rows = cursor.fetchall()
                alter_stmts = [
                    f'ALTER SEQUENCE "public"."{sn}" '
                    f"RESTART WITH "
                    f"{lv + (1 if ic else 0) + random.randint(50_000, 500_000)};"
                    for sn, lv, ic in rows
                ]
                cursor.execute("\n".join(alter_stmts))
