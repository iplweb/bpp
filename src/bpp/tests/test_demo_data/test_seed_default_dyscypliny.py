"""Testy seed_default_dyscypliny."""

from io import StringIO

import pytest
from django.core.management import call_command

from bpp.demo_data.default_dyscypliny import (
    DEFAULT_DYSCYPLINY,
    seed_default_dyscypliny,
)
from bpp.models import Dyscyplina_Naukowa


def test_default_dyscypliny_format():
    """Kazda dyscyplina ma kod N.N i niepusta nazwe."""
    assert len(DEFAULT_DYSCYPLINY) >= 50
    for kod, nazwa in DEFAULT_DYSCYPLINY:
        parts = kod.split(".")
        assert len(parts) == 2, f"Zly format kodu: {kod}"
        assert all(p.isdigit() for p in parts), f"Nie-cyfrowy kod: {kod}"
        # Dziedziny 1-8 (9 i 10 nie sa w const.DZIEDZINY):
        assert 1 <= int(parts[0]) <= 8, f"Kod dziedziny poza 1-8: {kod}"
        assert nazwa.strip(), f"Pusta nazwa dla kodu {kod}"


def test_default_dyscypliny_unique():
    """Kody i nazwy w slowniku sa unikalne."""
    kody = [kod for kod, _ in DEFAULT_DYSCYPLINY]
    nazwy = [nazwa for _, nazwa in DEFAULT_DYSCYPLINY]
    assert len(set(kody)) == len(kody), f"Duplikat kodu: {kody}"
    assert len(set(nazwy)) == len(nazwy), f"Duplikat nazwy: {nazwy}"


@pytest.mark.django_db
def test_seed_creates_all_dyscypliny():
    Dyscyplina_Naukowa.objects.all().delete()
    created, existed = seed_default_dyscypliny()
    assert created == len(DEFAULT_DYSCYPLINY)
    assert existed == 0
    assert Dyscyplina_Naukowa.objects.count() == len(DEFAULT_DYSCYPLINY)


@pytest.mark.django_db
def test_seed_is_idempotent():
    Dyscyplina_Naukowa.objects.all().delete()
    seed_default_dyscypliny()
    created, existed = seed_default_dyscypliny()
    assert created == 0
    assert existed == len(DEFAULT_DYSCYPLINY)
    assert Dyscyplina_Naukowa.objects.count() == len(DEFAULT_DYSCYPLINY)


@pytest.mark.django_db
def test_seeded_dyscypliny_pass_validator():
    """Kazda zaseedowana dyscyplina przechodzi waliduj_format_kodu_numer."""
    Dyscyplina_Naukowa.objects.all().delete()
    seed_default_dyscypliny()
    for d in Dyscyplina_Naukowa.objects.all():
        d.full_clean()


@pytest.mark.django_db
def test_command_runs():
    Dyscyplina_Naukowa.objects.all().delete()
    out = StringIO()
    call_command("seed_default_dyscypliny", stdout=out)
    output = out.getvalue()
    assert "dyscyplin" in output.lower()
    assert Dyscyplina_Naukowa.objects.count() == len(DEFAULT_DYSCYPLINY)
