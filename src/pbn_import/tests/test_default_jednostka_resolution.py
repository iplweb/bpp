"""Testy rozwiązywania domyślnej jednostki dla sesji importu PBN.

Regresja: krok ``publication_import`` rzucał ``ValueError`` ("Nie znaleziono
domyślnej jednostki...") gdy import startował od źródeł (z pominięciem kroku
``institution_setup``). Powód: formularz nowego importu zapisuje wybór do
``config["jednostka_domyslna_id"]``, a kroki czytały WYŁĄCZNIE
``config["default_jednostka_id"]`` (klucz zapisywany tylko przez
``institution_setup``). ``resolve_default_jednostka`` ujednolica odczyt.
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from pbn_import.models import ImportSession
from pbn_import.utils.institution_import import resolve_default_jednostka


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


def test_prefers_canonical_default_jednostka_id(session, uczelnia):
    """``default_jednostka_id`` (klucz institution_setup) ma pierwszeństwo."""
    canonical = baker.make(Jednostka, uczelnia=uczelnia)
    form_choice = baker.make(Jednostka, uczelnia=uczelnia)
    session.config = {
        "default_jednostka_id": canonical.pk,
        "jednostka_domyslna_id": form_choice.pk,
    }

    assert resolve_default_jednostka(session, uczelnia) == canonical


def test_falls_back_to_form_jednostka_domyslna_id(session, uczelnia):
    """Scenariusz buga: tylko klucz z formularza, bez institution_setup."""
    form_choice = baker.make(Jednostka, uczelnia=uczelnia)
    session.config = {"jednostka_domyslna_id": form_choice.pk}

    assert resolve_default_jednostka(session, uczelnia) == form_choice


def test_falls_back_to_uczelnia_aware_default(session, uczelnia):
    """Brak obu kluczy → find-or-create domyślnej jednostki TEJ uczelni."""
    result = resolve_default_jednostka(session, uczelnia)

    assert result is not None
    assert result.uczelnia_id == uczelnia.pk


def test_uczelnia_aware_fallback_reuses_existing_default(session, uczelnia):
    """Fallback nie duplikuje istniejącej "Jednostka Domyślna" tej uczelni."""
    existing = baker.make(Jednostka, nazwa="Jednostka Domyślna", uczelnia=uczelnia)

    result = resolve_default_jednostka(session, uczelnia)

    assert result == existing
    assert (
        Jednostka.objects.filter(nazwa__istartswith="Jednostka Domyślna").count() == 1
    )


def test_stale_id_falls_through_to_uczelnia_default(session, uczelnia):
    """Nieistniejące id w configu → nie wybuchamy, schodzimy do fallbacku."""
    session.config = {"default_jednostka_id": 9_999_999}

    result = resolve_default_jednostka(session, uczelnia)

    assert result is not None
    assert result.uczelnia_id == uczelnia.pk
