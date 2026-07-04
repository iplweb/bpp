"""Tests for the create_obca_jednostka management command."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from pbn_import.utils.institution_import import sprawdz_obca_jednostka


@pytest.fixture
def dwie_uczelnie(db):
    u1 = baker.make(Uczelnia, skrot="UML")
    u2 = baker.make(Uczelnia, skrot="UAFM")
    return u1, u2


def test_command_provisions_all_uczelnie(dwie_uczelnie):
    u1, u2 = dwie_uczelnie

    call_command("create_obca_jednostka")

    u1.refresh_from_db()
    u2.refresh_from_db()
    assert sprawdz_obca_jednostka(u1) is None
    assert sprawdz_obca_jednostka(u2) is None
    assert u1.obca_jednostka.nazwa == "Obca jednostka UML"
    assert u2.obca_jednostka.nazwa == "Obca jednostka UAFM"


def test_command_is_idempotent(dwie_uczelnie):
    call_command("create_obca_jednostka")
    call_command("create_obca_jednostka")

    assert Jednostka.objects.filter(skupia_pracownikow=False).count() == 2


def test_command_dry_run_does_not_write_and_signals(dwie_uczelnie):
    u1, _ = dwie_uczelnie

    with pytest.raises(CommandError):
        call_command("create_obca_jednostka", "--dry-run")

    u1.refresh_from_db()
    assert u1.obca_jednostka is None
    assert Jednostka.objects.filter(skupia_pracownikow=False).count() == 0


def test_command_dry_run_clean_is_silent(dwie_uczelnie):
    call_command("create_obca_jednostka")

    # Wszystko już skonfigurowane — dry-run nie sygnalizuje błędu (exit 0).
    call_command("create_obca_jednostka", "--dry-run")


def test_command_single_uczelnia_arg(dwie_uczelnie):
    u1, u2 = dwie_uczelnie

    call_command("create_obca_jednostka", str(u1.pk))

    u1.refresh_from_db()
    u2.refresh_from_db()
    assert u1.obca_jednostka is not None
    assert u2.obca_jednostka is None
