"""
Fixtures conftest.py - contains pytest hooks and additional fixtures.

Note: pytest_plugins declaration moved to top-level conftest.py (per pytest requirements).
Fixtures are loaded from submodules:
- conftest_models: Core model fixtures (uczelnia, wydzial, jednostka, autor)
- conftest_publications: Publication fixtures (wydawnictwo_ciagle, wydawnictwo_zwarte, etc.)
- conftest_system: System data fixtures (typy_odpowiedzialnosci, jezyki, etc.)
- conftest_browser: Browser/webtest fixtures
- conftest_disciplines: PBN discipline fixtures

Uwaga: monkey-patch ``TransactionTestCase._fixture_teardown`` (cascade
truncate + deadlock retry) siedzi w ``src/conftest.py`` — ten plik jest
auto-loadowany tylko dla testów w ``src/fixtures/``, a patch musi
działać globalnie.
"""

import os

import pytest

from bpp.tests.util import setup_model_bakery

# Note: pytest_plugins moved to top-level conftest.py as required by pytest

# Setup model_bakery
setup_model_bakery()


def pytest_configure():
    from django.conf import settings

    if hasattr(settings, "RAVEN_CONFIG"):
        del settings.RAVEN_CONFIG

    settings.TESTING = True
    # Flagi eager Celery ustawia teraz jednoznacznie settings/test.py
    # (CELERY_ALWAYS_EAGER / _TASK_ALWAYS_EAGER / _EAGER_PROPAGATES_EXCEPTIONS);
    # dawny re-set w tym hooku był redundantny — patrz audyt pkt 6.

    from bpp.models.cache import Autorzy, Rekord

    Rekord._meta.managed = True
    Autorzy._meta.managed = True


collect_ignore = [os.path.join(os.path.dirname(__file__), "media")]


def pytest_collection_modifyitems(items):
    # Dodaj marker "playwright" dla wszystkich testów używających fikstur 'page',
    # 'admin_page' lub 'zrodla_page', aby można było szybko uruchamiać wyłącznie
    # te testy lub je pomijać.
    #
    # NOTE: Serial marking was removed to enable parallelization.
    # Each pytest-xdist worker gets its own database (test_bpp_gw0, gw1, etc.),
    # so global .objects.all().delete() calls are safe - they only affect
    # that worker's database.

    for item in items:
        fixtures = getattr(item, "fixturenames", ())
        if "page" in fixtures or "admin_page" in fixtures or "zrodla_page" in fixtures:
            item.add_marker("playwright")
            # Ponów raz KAŻDY test przeglądarkowy (Playwright), który padł —
            # łapie niedeterministyczne flake'i (wait_for_* timeout,
            # ElementClickIntercepted, expect()→AssertionError), które nie
            # są regresją kodu. Zawężenie jest REALNE: markera dostają tylko
            # testy używające fikstur 'page'/'admin_page'/'zrodla_page', a
            # globalnego `--reruns` w pytest.ini NIE ma, więc testy
            # jednostkowe NIGDY nie są ponawiane — ich niedeterminizm to bug
            # do naprawy, nie do maskowania. `--only-rerun` w pytest.ini
            # dodatkowo ogranicza reruny do konkretnych wyjątków.
            #
            # Nie nadpisuj jawnego @pytest.mark.flaky(reruns=N) (np.
            # test_bpp_with_notifications ma reruns=3) — jego wyższa liczba
            # ponowień ma pierwszeństwo.
            if item.get_closest_marker("flaky") is None:
                item.add_marker(pytest.mark.flaky(reruns=1))


@pytest.fixture
def szablony():
    dirname = os.path.dirname(__file__)

    def template_n(elem):
        return f"{dirname}/../bpp/templates/{elem}"

    def create_template(Template, name):
        from dbtemplates.models import Template

        Template.objects.create(
            name=name,
            content=open(template_n(name)).read(),
        )

    def instaluj_szablony():
        from dbtemplates.models import Template

        create_template(Template, "opis_bibliograficzny.html")
        create_template(Template, "browse/praca_tabela.html")

        from bpp.models.szablondlaopisubibliograficznego import (
            SzablonDlaOpisuBibliograficznego,
        )

        SzablonDlaOpisuBibliograficznego.objects.create(
            model=None,
            template=Template.objects.get(name="opis_bibliograficzny.html"),
        )

    from dbtemplates.models import Template

    instaluj_szablony()
    return Template.objects
