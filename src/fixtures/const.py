"""Stałe używane przez fixtury oraz testy.

Moduł jest celowo odseparowany od ``fixtures.conftest_*``, żeby
``fixtures/__init__.py`` mógł re-eksportować stałe bez ściągania
za sobą modułów zadeklarowanych w ``pytest_plugins`` w
``src/conftest.py``. W przeciwnym razie import stałych typu
``from fixtures import NORMAL_DJANGO_USER_LOGIN`` pociągałby za
sobą ``conftest_browser`` PRZED rejestracją go przez pytest jako
plugin i odpalał ``PytestAssertRewriteWarning: Module already
imported so cannot be rewritten``.
"""

NORMAL_DJANGO_USER_LOGIN = "test_login_bpp"
NORMAL_DJANGO_USER_PASSWORD = "test_password"

JEDNOSTKA_UCZELNI = "Jednostka Uczelni"
JEDNOSTKA_PODRZEDNA = "Jednostka P-rzedna"
