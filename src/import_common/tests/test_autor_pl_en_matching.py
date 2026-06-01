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


# ---------------------------------------------------------------------------
# Klastry imion PL↔EN (hand-curated map)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "imie_w_bazie, imie_w_imporcie",
    [
        ("Krzysztof", "Christopher"),
        ("Christopher", "Krzysztof"),
        ("Paweł", "Paul"),
        ("Paul", "Paweł"),
        ("Maria", "Mary"),
        ("Małgorzata", "Margaret"),
        ("Elżbieta", "Elizabeth"),
        ("Łukasz", "Luke"),
        ("Łukasz", "Lucas"),
        ("Michał", "Michael"),
        ("Andrzej", "Andrew"),
        ("Tomasz", "Thomas"),
        ("Józef", "Joseph"),
        ("Aleksandra", "Alexandra"),
        ("Aleksander", "Alexander"),
        ("Ewa", "Eve"),  # uzupełnia v↔w (Ewa↔Eva)
    ],
)
def test_match_pl_en_name_clusters(imie_w_bazie, imie_w_imporcie):
    """Hand-curated mapa pokrywa typowe pary PL↔EN."""
    autor = baker.make(Autor, imiona=imie_w_bazie, nazwisko="Kowalski")
    assert matchuj_autora(imiona=imie_w_imporcie, nazwisko="Kowalski") == autor


@pytest.mark.django_db
def test_name_cluster_does_not_create_false_positive():
    """Imię spoza klastra nie matchuje przypadkowo: Marcin ≠ Mark."""
    baker.make(Autor, imiona="Marcin", nazwisko="Kowalski")
    assert matchuj_autora(imiona="Mark", nazwisko="Kowalski") is None


@pytest.mark.django_db
def test_cluster_combined_with_surname_unaccent():
    """Klaster imion + unaccent nazwiska razem: Christopher Marańda ↔ Krzysztof Maranda."""
    autor = baker.make(Autor, imiona="Krzysztof", nazwisko="Marańda")
    assert matchuj_autora(imiona="Christopher", nazwisko="Maranda") == autor


# ---------------------------------------------------------------------------
# Nazwiska z myślnikiem + diakrytyki (regresja: Lech-Marańda ↔ Lech-Maranda)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_match_hyphenated_surname_diacritics_pl_to_en():
    """BPP: Kowalska-Ńowak Ewa ↔ import: Kowalska-Nowak Eva.

    Regresja na zgłoszenie użytkownika: nazwisko z myślnikiem i diakrytykami
    nie dopasowywało się do anglojęzycznego zapisu (Marańda↔Maranda, Ewa↔Eva).
    """
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Kowalska-Ńowak")
    assert matchuj_autora(imiona="Eva", nazwisko="Kowalska-Nowak") == autor


@pytest.mark.django_db
def test_match_hyphenated_surname_diacritics_en_to_pl():
    """Odwrotnie: w bazie BPP siedzi Eva, import niesie polską pisownię."""
    autor = baker.make(Autor, imiona="Eva", nazwisko="Kowalska-Nowak")
    assert matchuj_autora(imiona="Ewa", nazwisko="Kowalska-Ńowak") == autor


@pytest.mark.django_db
def test_match_lech_maranda_literal():
    """Dokladny przypadek zgloszenia: Lech-Maranda Eva ↔ Lech-Marańda Ewa."""
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Marańda")
    assert matchuj_autora(imiona="Eva", nazwisko="Lech-Maranda") == autor
