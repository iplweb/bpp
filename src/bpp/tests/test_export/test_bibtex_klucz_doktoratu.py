"""Klucz BibTeX dla pracy doktorskiej/habilitacyjnej zawiera nazwisko autora.

Regresja (Rollbar #447): ``Praca_Doktorska.autorzy_dla_opisu()`` zwraca
``FakeSet`` — listę udającą queryset, bo doktorat ma dokładnie jednego autora
w polu ``autor``, a nie relację wiele-do-wielu. ``FakeSet`` nie miał metody
``first()``, więc ``generate_bibtex_key`` leciało na ``AttributeError``.
Wyjątek był połykany (``zaloguj_polkniety_wyjatek``), więc eksport nie padał —
tyle że klucz cichcem gubił nazwisko i zostawało samo ``<rok>_id<pk>``.
"""

import pytest

from bpp.export.bibtex import generate_bibtex_key


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
