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


# ============================================================================
# Regresja end-to-end: dokładnie ścieżka z produkcyjnego tracebacku.
#
# Test kontraktowy producent→konsument, którego BRAK pozwolił bugowi wejść na
# produkcję: formularz (producent) i kroki importu (konsument) były testowane
# OSOBNO, nikt nie przepuścił configu z formularza przez
# ``PublicationImporter._setup_uczelnia_and_jednostka`` (metoda, która rzucała
# ``ValueError`` — wcześniej 0 testów). Resolver-testy wyżej łapią dryf nazw
# kluczy, ale dopiero ten test pilnuje, że SAM krok importu nie przestanie
# używać resolvera.
# ============================================================================


@pytest.mark.django_db
def test_publication_import_setup_resolves_form_choice_without_institution_step(
    django_user_model,
    jezyki,
):
    """Import od źródeł (z pominięciem institution_setup) NIE rzuca ValueError.

    ``jezyki``: ``_setup_uczelnia_and_jednostka`` woła ``resolve_default_jezyk``
    → ``get_jezyk_polski`` (potrzebuje ``pol.``). Bez własnego seedu test
    zależałby od baseline, który pod równoległym xdist bywa wyTRUNCATE-owany
    przez sąsiedni test ``transaction=True`` — stąd fixture zamiast ambientu.

    Reprodukuje produkcyjny traceback: sesja ma w configu WYŁĄCZNIE klucz
    formularza ``jednostka_domyslna_id`` (krok ``institution_setup`` — jedyny
    historyczny zapis ``default_jednostka_id`` — nie biegł). Przed poprawką
    ``_setup_uczelnia_and_jednostka`` rzucał "Nie znaleziono domyślnej
    jednostki dla importu publikacji".
    """
    from pbn_api.models import Institution
    from pbn_import.utils.publication_import import PublicationImporter

    uczelnia = baker.make(Uczelnia, pbn_uid=baker.make(Institution))
    jednostka = baker.make(Jednostka, skupia_pracownikow=True, uczelnia=uczelnia)
    user = baker.make(django_user_model)
    # config dokładnie taki, jaki zapisywał formularz PRZED poprawką —
    # tylko klucz ``jednostka_domyslna_id``, bez kanonicznego ``default_*``.
    session = baker.make(
        ImportSession, user=user, config={"jednostka_domyslna_id": jednostka.pk}
    )

    importer = PublicationImporter(session, client=None, uczelnia=uczelnia)

    result = importer._setup_uczelnia_and_jednostka()

    assert result == uczelnia
    assert importer.default_jednostka == jednostka
