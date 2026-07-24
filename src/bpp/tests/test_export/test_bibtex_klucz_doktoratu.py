"""Klucz BibTeX dla pracy doktorskiej/habilitacyjnej zawiera nazwisko autora.

Regresja (Rollbar #447): ``Praca_Doktorska.autorzy_dla_opisu()`` zwraca
``FakeSet`` — listę udającą queryset, bo doktorat ma dokładnie jednego autora
w polu ``autor``, a nie relację wiele-do-wielu. ``FakeSet`` nie miał metody
``first()``, więc ``generate_bibtex_key`` leciało na ``AttributeError``.
Wyjątek był połykany (``zaloguj_polkniety_wyjatek``), więc eksport nie padał —
tyle że klucz cichcem gubił nazwisko i zostawało samo ``<rok>_id<pk>``.
"""

import pytest
from model_bakery import baker

from bpp.export.bibtex import generate_bibtex_key
from bpp.models import Autor, Wydawnictwo_Ciagle
from bpp.models.util import prefetch_dane_strony_rekordu


@pytest.mark.django_db
def test_klucz_bibtex_doktoratu_zawiera_nazwisko_autora(doktorat, autor_jan_kowalski):
    doktorat.autor = autor_jan_kowalski
    doktorat.rok = 2020
    doktorat.save()

    klucz = generate_bibtex_key(doktorat)

    assert klucz == f"Kowalski_2020_id{doktorat.pk}"


@pytest.mark.django_db
def test_klucz_bibtex_habilitacji_zawiera_nazwisko_autora(
    habilitacja, autor_jan_kowalski
):
    habilitacja.autor = autor_jan_kowalski
    habilitacja.rok = 2021
    habilitacja.save()

    klucz = generate_bibtex_key(habilitacja)

    assert klucz == f"Kowalski_2021_id{habilitacja.pk}"


@pytest.mark.django_db
def test_klucz_bibtex_dziala_gdy_autorzy_sa_zwykla_lista(typy_odpowiedzialnosci):
    """``autorzy_dla_opisu()`` bywa ZWYKŁĄ LISTĄ, nie tylko querysetem.

    ``bpp.models.util`` zwraca stamtąd trzy różne kształty: queryset, ``[]``
    dla obiektu bez ``pk`` oraz listę podstawioną przez
    ``prefetch_dane_strony_rekordu`` (``Prefetch(to_attr=...)``). Czwarty to
    ``FakeSet`` doktoratu. Żaden z listowych nie ma ``first()``, więc
    naprawienie samego ``FakeSet`` zostawiłoby tę samą pułapkę obok.
    """
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    wyd = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Artykuł", rok=2019)
    wyd.dodaj_autora(autor, baker.make("bpp.Jednostka"))

    prefetch_dane_strony_rekordu(wyd)
    assert isinstance(wyd.autorzy_dla_opisu(), list), (
        "prefetch miał podstawić listę — bez tego test nie bada tej ścieżki"
    )

    assert generate_bibtex_key(wyd) == f"Nowak_2019_id{wyd.pk}"
