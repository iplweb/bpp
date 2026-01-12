"""
Fixtures conftest.py - contains pytest hooks and additional fixtures.

Note: pytest_plugins declaration moved to top-level conftest.py (per pytest requirements).
Fixtures are loaded from submodules:
- conftest_models: Core model fixtures (uczelnia, wydzial, jednostka, autor)
- conftest_publications: Publication fixtures (wydawnictwo_ciagle, wydawnictwo_zwarte, etc.)
- conftest_system: System data fixtures (typy_odpowiedzialnosci, jezyki, etc.)
- conftest_browser: Browser/Selenium fixtures
- conftest_disciplines: PBN discipline fixtures
"""

import os
import random
import time

import pytest
from dbtemplates.models import Template
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.db.utils import OperationalError
from django.test import TransactionTestCase

from bpp.models import Kierunek_Studiow
from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego
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
    # Dodaj marker "selenium" dla wszystkich testów uzywających fikstur 'browser'
    # lub 'admin_browser', aby można było szybko uruchamiać wyłacznie te testy
    # lub nie uruchamiać ich

    flaky_test = pytest.mark.flaky(reruns=5)

    for item in items:
        fixtures = getattr(item, "fixturenames", ())
        if "page" in fixtures or "admin_page" in fixtures or "zrodla_page" in fixtures:
            item.add_marker("playwright")
            item.add_marker(pytest.mark.serial)


#
# Monkeypatch fixture-teardown to allow TRUNCATE
#


def _fixture_teardown(self):
    # Allow TRUNCATE ... CASCADE and don't emit the post_migrate signal
    # when flushing only a subset of the apps
    for db_name in self._databases_names(include_mirrors=False):
        # Flush the database
        inhibit_post_migrate = (
            self.available_apps is not None
            or (  # Inhibit the post_migrate signal when using serialized
                # rollback to avoid trying to recreate the serialized data.
                self.serialized_rollback
                and hasattr(connections[db_name], "_test_serialized_contents")
            )
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


@pytest.fixture
def szablony():
    dirname = os.path.dirname(__file__)

    def template_n(elem):
        return f"{dirname}/../bpp/templates/{elem}"

    def create_template(Template, name):
        Template.objects.create(
            name=name,
            content=open(template_n(name)).read(),
        )

    def instaluj_szablony():
        create_template(Template, "opis_bibliograficzny.html")
        create_template(Template, "browse/praca_tabela.html")

        SzablonDlaOpisuBibliograficznego.objects.create(
            model=None,
            template=Template.objects.get(name="opis_bibliograficzny.html"),
        )

    instaluj_szablony()
    return Template.objects


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    from denorm import denorms

    with django_db_blocker.unblock():
        denorms.install_triggers()


@pytest.fixture(scope="function")
def django_db_setup(django_db_setup, django_db_blocker):  # noqa
    from denorm import denorms

    with django_db_blocker.unblock():
        denorms.install_triggers()


@pytest.fixture(scope="class")
def django_db_setup(django_db_setup, django_db_blocker):  # noqa
    from denorm import denorms

    with django_db_blocker.unblock():
        denorms.install_triggers()


@pytest.mark.django_db
@pytest.fixture
def kierunek_studiow(wydzial):
    return Kierunek_Studiow.objects.get_or_create(
        wydzial=wydzial,
        nazwa="memetyka użytkowa",
        skrot="mem. uż.",
        opis="testowy kierunek studiów",
    )[0]
