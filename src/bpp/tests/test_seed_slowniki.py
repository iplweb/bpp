"""``seed_slowniki`` odtwarza słowniki zmiecione przez ``TRUNCATE``.

``TransactionTestCase._fixture_teardown`` czyści całą bazę i emituje
``post_migrate``; bez tego receivera kolejne testy na tym samym workerze
widzą puste słowniki. Dotąd wracały tylko rodzaje jednostek, więc test
importera (``importer_publikacji``) szukający języka po ``kod_bcp47`` padał,
gdy tylko trafił w shardzie za testem transakcyjnym.
"""

import pytest
from django.apps import apps

from bpp.models import Jezyk, RodzajJednostki
from bpp.seed_slowniki import seed_slowniki


def _odtworz():
    seed_slowniki(sender=apps.get_app_config("bpp"))


@pytest.mark.django_db
def test_seed_odtwarza_angielski_z_kodem_bcp47():
    Jezyk.objects.filter(skrot="ang.").delete()

    _odtworz()

    assert Jezyk.objects.filter(kod_bcp47="en").exists()


@pytest.mark.django_db
def test_seed_odtwarza_jezyki_z_fixture():
    Jezyk.objects.all().delete()

    _odtworz()

    kody = set(Jezyk.objects.exclude(kod_bcp47="").values_list("kod_bcp47", flat=True))
    assert {"pl", "en", "de", "fr", "es", "ru", "it"} <= kody


@pytest.mark.django_db
def test_seed_jest_idempotentny():
    _odtworz()
    ile = Jezyk.objects.count()

    _odtworz()

    assert Jezyk.objects.count() == ile


@pytest.mark.django_db
def test_seed_nadal_odtwarza_rodzaje_jednostek():
    RodzajJednostki.objects.all().delete()

    _odtworz()

    assert RodzajJednostki.objects.exists()
