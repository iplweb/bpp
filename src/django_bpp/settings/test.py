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

from .local import *  # noqa
from .local import INSTALLED_APPS, MIDDLEWARE  # noqa

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
