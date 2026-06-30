"""
Charakteryzacyjne testy `analiza_duplikatow` przypinające BIEŻĄCE zachowanie
przed refaktorem obniżającym złożoność cyklomatyczną (C901).

Pokrywają gałęzie nieobjęte pozostałymi plikami testowymi:
- ścieżka błędu (brak rekordu w BPP dla Scientist),
- analiza płci (RÓŻNA PŁEĆ → kara -100),
- dokładny shape zwracanego słownika + dokładna wartość `pewnosc`.

Wartości `pewnosc` są przypięte dokładnie (a nie tylko ">=") aby refaktor
nie mógł niezauważalnie zmienić scoringu.
"""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils import analiza_duplikatow
from pbn_api.models import OsobaZInstytucji, Scientist

pytestmark = pytest.mark.django_db


def test_analiza_duplikatow_brak_rekordu_w_bpp():
    """Scientist bez powiązanego Autora → słownik z błędem."""
    scientist = baker.make(Scientist)
    osoba = baker.make(OsobaZInstytucji, personId=scientist)

    wynik = analiza_duplikatow(osoba)

    assert wynik == {"error": "Nie można znaleźć głównego autora"}


def test_analiza_duplikatow_dict_shape_i_dokladna_pewnosc(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Pełne dopasowanie: przypięty kształt słownika + dokładny scoring.

    glowny: 'Jan Marian' / 'Gal-Cisoń' / 'dr hab.', bez ORCID, bez publikacji.
    duplikat: identyczne imiona/nazwisko, tytuł 'dr' (default), bez ORCID.

    Scoring (bieżący):
      +10  mało publikacji (0)
      -15  różny tytuł naukowy ('dr' vs 'dr hab.')
      +40  identyczne nazwisko
      +60  wspólne imię (2) -> 30*2
      +10  pasujące inicjały (2) -> 5*2
      = 105
    """
    duplikat = autor_maker(imiona="Jan Marian", nazwisko="Gal-Cisoń")

    wynik = analiza_duplikatow(osoba_z_instytucji)

    assert set(wynik.keys()) == {
        "glowny_autor",
        "duplikaty",
        "analiza",
        "ilosc_duplikatow",
    }
    assert wynik["glowny_autor"] == glowny_autor
    assert wynik["ilosc_duplikatow"] == 1
    assert len(wynik["analiza"]) == 1

    a = wynik["analiza"][0]
    assert a["autor"] == duplikat
    assert a["pewnosc"] == 105
    assert a["powody_podobienstwa"] == [
        "mało publikacji (0) - prawdopodobny duplikat",
        "różny tytuł naukowy - mniej prawdopodobny duplikat",
        "identyczne nazwisko",
        "wspólne imię (2)",
        "pasujące inicjały (2)",
    ]


def test_analiza_duplikatow_rozna_plec_kara(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Różna płeć (Maria/FEMALE vs Mariusz/MALE) → kara -100, reason RÓŻNA PŁEĆ.

    Nazwiska identyczne, imiona przechodzą hard-rejection przez wspólny
    3-znakowy prefiks 'mar'. Scoring:
      -100 RÓŻNA PŁEĆ
      +10  mało publikacji (0)
      -15  różny tytuł naukowy
      +40  identyczne nazwisko
      +15  podobne imię (1)
      +5   pasujące inicjały (1)
      = -45
    """
    glowny_autor.imiona = "Maria"
    glowny_autor.save()

    duplikat = autor_maker(imiona="Mariusz", nazwisko="Gal-Cisoń")

    wynik = analiza_duplikatow(osoba_z_instytucji)

    a = next((x for x in wynik["analiza"] if x["autor"] == duplikat), None)
    assert a is not None
    assert any(powod.startswith("RÓŻNA PŁEĆ:") for powod in a["powody_podobienstwa"])
    assert a["pewnosc"] == -45


def test_analiza_duplikatow_brak_duplikatow(osoba_z_instytucji, glowny_autor, tytuly):
    """Brak kandydatów → puste listy, ilosc_duplikatow == 0."""
    wynik = analiza_duplikatow(osoba_z_instytucji)

    assert wynik["glowny_autor"] == glowny_autor
    assert wynik["ilosc_duplikatow"] == 0
    assert wynik["analiza"] == []
    assert list(wynik["duplikaty"]) == []
