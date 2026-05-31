"""Public symbols re-eksportowane z ``fixtures`` do użycia w testach.

Tu wolno importować WYŁĄCZNIE moduły wolne od Django. Rootdir-owy
``conftest.py`` robi ``from fixtures import *``, a ``pytest-testcontainers-
django`` preloaduje ten conftest ZANIM ``django.setup()`` się wykona
(hook ``pytest_load_initial_conftests``, tryfirst). Każdy top-levelowy
import modelu w tym łańcuchu wybucha ``AppRegistryNotReady`` i psuje
preload (regresja patch'owana wielokrotnie — patrz
``src/bpp/tests/test_conftest_preload_safety.py``).

Dlatego moduły z fiksturami, które importują modele (``pbn_api``,
``wydawnictwa``, ``conftest_*``) NIE są tu importowane — rejestrujemy je
jako pytest plugins w ``conftest.py`` (``pytest_plugins = [...]``),
ładowane DOPIERO po ``django.setup()``. Eager import pociągałby je też
PRZED rejestracją przez pytest, skutkując ``PytestAssertRewriteWarning:
Module already imported so cannot be rewritten``.

Niefiksturowe symbole tych modułów (helpery ``pbn_*_json``, stałe
``MOCK_*``) importuj wprost: ``from fixtures.pbn_api import ...``.

Stałe (``NORMAL_DJANGO_USER_*``, ``JEDNOSTKA_*``) trzymamy w
``fixtures.const`` — wolnym od Django.
"""

from .const import *  # noqa
