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
import random

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
    settings.CELERY_ALWAYS_EAGER = True
    settings.CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

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

        from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego
        SzablonDlaOpisuBibliograficznego.objects.create(
            model=None,
            template=Template.objects.get(name="opis_bibliograficzny.html"),
        )

    from dbtemplates.models import Template
    instaluj_szablony()
    return Template.objects


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    from denorm import denorms
    from django.db import connection

    with django_db_blocker.unblock():
        denorms.install_triggers()

        # Przesuń każdą sekwencję w public o losową wartość z zakresu
        # [50 000, 500 000], niezależnie per sekwencja. Cel: nie pozwolić
        # testom dostawać 1-/2-cyfrowych ID, które maskują bugi zależne
        # od szerokości ID (padding, długość slugów, przekroczenia granicy
        # cyfr). Różne offsety per tabela dodatkowo rozsynchronizowują
        # relacje między ID różnych tabel, co demaskuje testy zakładające
        # np. autor.pk == jednostka.pk.
        #
        # Ziarno PRNG: `random` w tym module jest seedowane przez
        # pytest-randomly (jeśli zainstalowane) albo systemowo. Żeby
        # zreprodukować konkretny run, wystarczy ten sam seed.
        print(
            f"[conftest] bump sekwencji, seed random.getstate() hash="
            f"{hash(random.getstate()) & 0xFFFF_FFFF:#010x}"
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT schemaname, sequencename FROM pg_sequences "
                "WHERE schemaname = 'public'"
            )
            for schema, name in cursor.fetchall():
                cursor.execute(
                    f'SELECT last_value, is_called FROM "{schema}"."{name}"'
                )
                last_value, is_called = cursor.fetchone()
                next_val = last_value + (1 if is_called else 0)
                offset = random.randint(50_000, 500_000)
                cursor.execute(
                    f'ALTER SEQUENCE "{schema}"."{name}" '
                    f"RESTART WITH {next_val + offset}"
                )
