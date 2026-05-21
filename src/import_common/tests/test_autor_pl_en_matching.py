"""Matchowanie autorów po wariantach pisowni polsko-angielskiej.

Testy dla `matchuj_autora` w sytuacji, gdy importowane dane przychodzą
ze źródła anglojęzycznego (CrossRef, DSpace EN), a w BPP siedzi polska
pisownia: diakrytyki (Marańda↔Maranda) oraz transliteracja v↔w
(Eva↔Ewa, Viktor↔Wiktor).
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from import_common.core import matchuj_autora


@pytest.mark.django_db
def test_match_diacritics_only():
    """Marańda ↔ Maranda — sam unidecode-fold nazwiska."""
    autor = baker.make(Autor, imiona="Adam", nazwisko="Marańda")
    assert matchuj_autora(imiona="Adam", nazwisko="Maranda") == autor


@pytest.mark.django_db
def test_match_v_to_w_first_name():
    """Eva (źródło EN) ↔ Ewa (BPP) — regula v↔w na imieniu."""
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Kowalska")
    assert matchuj_autora(imiona="Eva", nazwisko="Kowalska") == autor


@pytest.mark.django_db
def test_match_w_to_v_first_name():
    """Wiktor (BPP) ↔ Viktor (źródło EN) — działa w obie strony."""
    autor = baker.make(Autor, imiona="Wiktor", nazwisko="Nowak")
    assert matchuj_autora(imiona="Viktor", nazwisko="Nowak") == autor


@pytest.mark.django_db
def test_match_full_pl_en_case():
    """Literalny przypadek użytkownika: Ewa Marańda ↔ Eva Maranda."""
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Marańda")
    assert matchuj_autora(imiona="Eva", nazwisko="Maranda") == autor


@pytest.mark.django_db
def test_v_to_w_not_applied_to_surname():
    """Regula v↔w nie dotyczy nazwisk: Wojciechowski nie pasuje do Vojciechowski.

    Polskie nazwiska mają "w" jako autentyczną literę; transliteracja
    pomyłkowo łączyłaby różnych ludzi.
    """
    baker.make(Autor, imiona="Jan", nazwisko="Wojciechowski")
    assert matchuj_autora(imiona="Jan", nazwisko="Vojciechowski") is None


@pytest.mark.django_db
def test_existing_iexact_match_still_works():
    """Brak regresji: gdy iexact wystarczy, fallback PL↔EN się nie aktywuje."""
    autor = baker.make(Autor, imiona="Anna", nazwisko="Nowak")
    assert matchuj_autora(imiona="Anna", nazwisko="Nowak") == autor


@pytest.mark.django_db
def test_ambiguous_pl_en_match_returns_none():
    """Gdy fallback PL↔EN trafia w wielu kandydatów — zwracamy None.

    Decyzja należy do użytkownika (UI pokazuje listę),
    nie chcemy odgadywać.
    """
    baker.make(Autor, imiona="Ewa", nazwisko="Marańda")
    baker.make(Autor, imiona="Eva", nazwisko="Maranda")
    assert matchuj_autora(imiona="Eva", nazwisko="Maranda") is not None
    # ^ exact match z drugą — to nie jest ambiguity (iexact pierwszy)

    # Prawdziwy ambiguity: dwóch różnych Ewa/Eva o tym samym nazwisku
    Autor.objects.all().delete()
    baker.make(Autor, imiona="Ewa", nazwisko="Marańda")
    baker.make(Autor, imiona="Eva", nazwisko="Marańda")
    assert matchuj_autora(imiona="Eva", nazwisko="Maranda") is None


@pytest.mark.django_db
def test_empty_inputs_return_none():
    """Defensywnie: pusty input nie wybucha."""
    baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    assert matchuj_autora(imiona="", nazwisko="") is None
    assert matchuj_autora(imiona=None, nazwisko=None) is None
