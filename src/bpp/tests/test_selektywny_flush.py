"""Selektywne sprzątanie po teście transakcyjnym (``fixtures.selektywny_flush``)
przywraca DOKŁADNIE stan po pełnym flush-u."""

import pytest
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from fixtures import selektywny_flush as sf


def _stan_s0_po_pelnym_flushu():
    call_command(
        "flush",
        verbosity=0,
        interactive=False,
        reset_sequences=False,
        allow_cascade=True,
    )
    sf.zbuduj_stan("default")
    stan = sf._STAN["default"]
    return stan, sf.odcisk_wszystkich(connection, stan.kandydaci)


@pytest.mark.django_db(transaction=True)
def test_sprzataj_przywraca_s0_po_zmianach_domenowych_i_zasiewanych():
    stan, s0 = _stan_s0_po_pelnym_flushu()

    baker.make("bpp.Wydawnictwo_Ciagle")
    baker.make("bpp.Autor")
    Group.objects.create(name="grupa-z-testu")
    Site.objects.create(domain="test.example.org", name="test")
    Site.objects.exclude(domain="test.example.org").update(name="zmieniona")

    assert sf.sprzataj("default") > 0
    assert sf.odcisk_wszystkich(connection, stan.kandydaci) == s0
    assert not Group.objects.filter(name="grupa-z-testu").exists()


@pytest.mark.django_db(transaction=True)
def test_sprzataj_bez_zmian_nic_nie_robi():
    stan, s0 = _stan_s0_po_pelnym_flushu()

    assert sf.sprzataj("default") == 0
    assert sf.odcisk_wszystkich(connection, stan.kandydaci) == s0


@pytest.mark.django_db(transaction=True)
def test_sprzataj_bez_s0_wymaga_pelnego_flusha():
    sf.zapomnij("default")
    with pytest.raises(sf.PotrzebnyPelnyFlush):
        sf.sprzataj("default")
