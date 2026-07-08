# Konfiguracja dla testów (pytest).
#
# Cienka warstwa nad ``local.py``: testy dziedziczą całą konfigurację
# deweloperską (DummyCache, DEBUG, eager Celery, easyaudit, dev-helpers),
# a tutaj nakładamy WYŁĄCZNIE rzeczy specyficzne dla przebiegu testowego.
# Wybierane przez ``--ds=django_bpp.settings.test`` w ``pytest.ini``.
#
# Wcześniej te modyfikacje siedziały w ``local.py`` pod strażą
# ``if "pytest" in sys.modules`` — bo ``local.py`` pełnił podwójną rolę
# (dev + testy). Po rozdzieleniu strażnik jest zbędny: ten plik ładuje się
# tylko dla testów, więc nakładamy je bezwarunkowo.

import os
import tempfile

from .local import *  # noqa
from .local import CACHES, INSTALLED_APPS, LIVEOPS, MIDDLEWARE  # noqa

# MEDIA_ROOT per-proces (worker xdist). Domyślnie testy dziedziczyły
# MEDIA_ROOT = <repo>/src/media z local.py — JEDEN wspólny katalog w drzewie
# źródeł dla wszystkich workerów. Skutki (audyt
# docs/deweloper/audyt-testy-rownoleglosc-2026-07.md, pkt 1): kolizje plików
# między workerami (maskowane sufiksami dedupe FileSystemStorage — ~1800
# wyciekłych plików) oraz, groźniejsze, pytest importował uploadowany do
# MEDIA_ROOT conftest.py (obok powstawał __pycache__), co potrafiło wywalić
# kolekcję całej suity ImportError-em. Każdy worker dostaje własny izolowany
# tempdir (mkdtemp — dwie równoległe sesje pytest na jednym hoście się nie
# zderzą), a ścieżka jest PINOWANA w zmiennej środowiskowej per worker.
# Env var (a nie PID w nazwie katalogu): subprocess Daphne
# (channels_live_server) na macOS startuje przez multiprocessing *spawn*
# i RE-IMPORTUJE settings z nowym PID-em — klucz z PID-em dałby mu inny
# MEDIA_ROOT niż workerowi pytest (a na Linuksie/CI fork dziedziczy moduł
# → ten sam; rozjazd mac-vs-CI). Env var dziedziczą oba mechanizmy, więc
# worker i jego dzieci widzą ten sam katalog. Nazwa zmiennej zawiera id
# workera, bo kontroler xdist też importuje settings (jako "master")
# i jego wartość nie może przeciec do workerów gwN przez dziedziczone
# środowisko.
_media_worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
_media_env = f"DJANGO_BPP_TEST_MEDIA_ROOT_{_media_worker}"
MEDIA_ROOT = os.environ.get(_media_env)
if not MEDIA_ROOT:
    MEDIA_ROOT = tempfile.mkdtemp(prefix=f"bpp-test-media-{_media_worker}-")
    os.environ[_media_env] = MEDIA_ROOT
os.makedirs(MEDIA_ROOT, exist_ok=True)
SENDFILE_ROOT = MEDIA_ROOT

# Flagi eager Celery jawnie i jednoznacznie w testach. base.py ustawia je pod
# TESTING, ale local.py:64 bezwarunkowo resetuje CELERY_ALWAYS_EAGER = False
# (podwójna rola local.py: dev + testy). Fallback = .delay() cicho publikuje do
# wspólnego brokera Redis DB 1 bez konsumenta → task nigdy się nie wykona
# (silent no-op zależny od kolejności). Patrz audyt pkt 6.
CELERY_ALWAYS_EAGER = True
CELERY_TASK_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

# constance_cache (Redis DB 8) — per-worker KEY_PREFIX. Prefiks istniał
# (commit 137fec4df) i zginął w refaktorze test/local 55e0b1aa6 — regresja z
# audytu pkt 7. Bez niego pierwszy realny klucz constance wskrzesza
# cross-worker leak (worker A cache'uje wartość, worker B ją czyta mimo innej
# własnej bazy). Kopiujemy strukturę, by nie mutować obiektów współdzielonych
# z local.py.
CACHES = {**CACHES}
CACHES["constance_cache"] = {
    **CACHES["constance_cache"],
    "KEY_PREFIX": os.environ.get("PYTEST_XDIST_WORKER", "master"),
}

# django-liveops: w testach uruchamiaj operacje SYNCHRONICZNIE w wątku
# żądania (bez Redis/Celery workera). run() biegnie od razu, p.track/p.result
# działają, a terminalny stan (result_context/duplicates_found) zapisuje się
# zanim asserty go czytają. Push przez WebSocket i tak trafia w pustą grupę —
# nieszkodliwe dla testów logiki skanu.
LIVEOPS = {**LIVEOPS, "RUNNER": "eager"}

# Setup wizard middleware nie ma sensu w testach (i przeszkadza fixture'om).
MIDDLEWARE = [
    m for m in MIDDLEWARE if m != "first_run_wizard.middleware.FirstRunWizardMiddleware"
]

# Testy nie powinny korzystać z cacheops — paczka monkey-patchuje
# globalnie Manager.get / QuerySet.* i potrafi wywalać
# NotSupportedError / ForeignKeyViolation przy losowej kolejności
# xdist workerów (queryset-y dzielą stan `combinator` między testami).
# Usunięcie cacheops z INSTALLED_APPS wyłącza monkey-patching — produkcja
# dalej używa cacheops z pełnym CACHEOPS dict w production.py.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "cacheops"]

# Sam INSTALLED_APPS-prune NIE wystarczy: dekorator @cached (cacheops.simple)
# jest niezależny od `cacheops` w INSTALLED_APPS, nadal pisze/czyta z Redis
# db=7. Pod xdist Redis jest jeden na sesję pytest, więc workery widzą
# nawzajem swoje cache'owane wyniki — np. `get_uczelnia_context_data`
# cache'uje `recently_updated` z PK-ami publikacji workera A, worker B
# renderuje homepage z tymi linkami i potem dostaje 404 na
# `/bpp/rekord/<ct>,<pk>/`. Wyłączenie CACHEOPS_ENABLED zamienia `@cached`
# w no-op (cacheops/simple.py:54) i propaguje się też na `invalidate_*`,
# które same sprawdzają tę flagę.
CACHEOPS_ENABLED = False

# django-axes wyłączone w testach: Client.login() woła authenticate() bez
# `request`, na co AxesStandaloneBackend reaguje AxesBackendRequestParameterRequired
# i wywróciłby wszystkie fixture'y logujące się przez client.login(). Testy, które
# faktycznie sprawdzają lockout (src/bpp/tests/test_axes_lockout.py), włączają axes
# punktowo przez @override_settings(AXES_ENABLED=True) i logują się POST-em do
# widoku logowania (który request przekazuje).
AXES_ENABLED = False
