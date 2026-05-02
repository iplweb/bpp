"""Charakterystyczne testy dla `ewaluacja_dwudyscyplinowcy.core`.

Patrz ANALYSIS.md #5 (2026-05-02) — moduł produkuje dane do oświadczeń
dla autorów z dwiema dyscyplinami i wcześniej nie miał żadnych testów.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from ewaluacja_dwudyscyplinowcy.core import (
    _oblicz_sloty_dla_publikacji,
    pobierz_autorow_z_dwiema_dyscyplinami,
)


@pytest.mark.django_db
def test_pobierz_autorow_pusta_baza_zwraca_pusto():
    assert pobierz_autorow_z_dwiema_dyscyplinami(lata=[2024]) == {}


@pytest.mark.django_db
def test_pobierz_autorow_pomija_autora_z_jedna_dyscyplina(dyscyplina1):
    autor = baker.make(Autor)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dyscyplina1,
        # bez subdyscyplina_naukowa — to nie jest dwudyscyplinowiec
    )
    assert pobierz_autorow_z_dwiema_dyscyplinami(lata=[2024]) == {}


@pytest.mark.django_db
def test_pobierz_autorow_zwraca_dwudyscyplinowca(dyscyplina1, dyscyplina2):
    autor = baker.make(Autor)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    result = pobierz_autorow_z_dwiema_dyscyplinami(lata=[2024])

    assert autor.pk in result
    assert result[autor.pk]["autor"] == autor
    assert 2024 in result[autor.pk]["lata"]
    assert result[autor.pk]["lata"][2024]["dyscyplina_glowna"] == dyscyplina1
    assert result[autor.pk]["lata"][2024]["subdyscyplina"] == dyscyplina2


@pytest.mark.django_db
def test_pobierz_autorow_agreguje_lata(dyscyplina1, dyscyplina2):
    """Jeden autor z dwiema dyscyplinami w wielu latach — wszystkie lata
    pojawiają się pod tym samym autor_id."""
    autor = baker.make(Autor)
    for rok in (2023, 2024):
        Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
            subdyscyplina_naukowa=dyscyplina2,
        )

    result = pobierz_autorow_z_dwiema_dyscyplinami(lata=[2023, 2024, 2025])

    assert set(result[autor.pk]["lata"].keys()) == {2023, 2024}


@pytest.mark.django_db
def test_pobierz_autorow_lata_default_to_2022_2025(dyscyplina1, dyscyplina2):
    """Bez argumentu — domyślnie 2022-2025 (włącznie)."""
    autor = baker.make(Autor)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2025,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2021,  # poza domyślnym zakresem
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    result = pobierz_autorow_z_dwiema_dyscyplinami()

    assert 2025 in result[autor.pk]["lata"]
    assert 2021 not in result[autor.pk]["lata"]


@pytest.mark.django_db
def test_oblicz_sloty_None_gdy_publikacja_nieadaptowalna(dyscyplina1):
    """`_oblicz_sloty_dla_publikacji` zwraca None gdy ISlot rzuca
    CannotAdapt (np. publikacja bez punktacji za rok). Charakteryzujemy
    OBECNE zachowanie — silent catch jest udokumentowany w ANALYSIS.md #5
    jako technical debt, ale na razie taka jest semantyka."""

    class FakePublikacja:
        autorzy_set = type("AutorzySet", (), {"all": staticmethod(lambda: [])})()

    # ISlot(FakePublikacja()) podniesie CannotAdapt — funkcja zwraca None
    result = _oblicz_sloty_dla_publikacji(FakePublikacja(), dyscyplina1)
    assert result is None
