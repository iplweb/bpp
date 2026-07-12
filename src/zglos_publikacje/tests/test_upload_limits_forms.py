"""Testy jednostkowe limitów uploadu na poziomie walidacji formularza (A2).

Czysta walidacja — bez bazy. Nie alokujemy realnych 20 MB: używamy
SimpleUploadedFile z nadpisanym atrybutem `.size`.
"""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from zglos_publikacje.forms import MultipleFileField
from zglos_publikacje.validators import (
    MAX_LICZBA_PLIKOW,
    MAX_ROZMIAR_PLIKU,
    validate_file_size,
)


def _plik(name="a.pdf", size=1024):
    """Zwróć SimpleUploadedFile z nadpisanym `.size` (bez alokacji)."""
    f = SimpleUploadedFile(name, b"x", content_type="application/pdf")
    f.size = size
    return f


def test_validate_file_size_odrzuca_za_duzy_plik():
    f = _plik(size=MAX_ROZMIAR_PLIKU + 1)
    with pytest.raises(ValidationError):
        validate_file_size(f)


def test_validate_file_size_odrzuca_21mb():
    f = _plik(size=21 * 1024 * 1024)
    with pytest.raises(ValidationError):
        validate_file_size(f)


def test_validate_file_size_przepuszcza_19mb():
    f = _plik(size=19 * 1024 * 1024)
    # Nie powinno rzucić.
    validate_file_size(f)


def test_validate_file_size_przepuszcza_dokladnie_limit():
    f = _plik(size=MAX_ROZMIAR_PLIKU)
    validate_file_size(f)


def test_multiplefield_clean_odrzuca_zbyt_wiele_plikow():
    field = MultipleFileField(required=False)
    pliki = [_plik(name=f"p{i}.pdf") for i in range(MAX_LICZBA_PLIKOW + 1)]
    with pytest.raises(ValidationError):
        field.clean(pliki)


def test_multiplefield_clean_przepuszcza_maksymalna_liczbe():
    field = MultipleFileField(required=False)
    pliki = [_plik(name=f"p{i}.pdf") for i in range(MAX_LICZBA_PLIKOW)]
    result = field.clean(pliki)
    assert isinstance(result, list)
    assert len(result) == MAX_LICZBA_PLIKOW


def test_multiplefield_clean_pojedynczy_plik_zachowuje_ksztalt():
    """Nie-lista → pojedyncza wartość (nie lista); limit liczby nie wywala."""
    field = MultipleFileField(required=False)
    f = _plik()
    result = field.clean(f)
    assert not isinstance(result, (list, tuple))
    assert result is f


def test_multiplefield_clean_pusta_lista_ok():
    field = MultipleFileField(required=False)
    assert field.clean([]) == []


def test_multiplefield_clean_none_ok():
    field = MultipleFileField(required=False)
    # None (brak pliku, required=False) nie wywala limitu liczby.
    assert field.clean(None) is None


def test_multiplefield_clean_odrzuca_oversized_plik_na_liscie():
    """Per-plik validate_file_size odpala przez validators pola."""
    field = MultipleFileField(required=False, validators=[validate_file_size])
    pliki = [_plik(name="ok.pdf"), _plik(name="big.pdf", size=21 * 1024 * 1024)]
    with pytest.raises(ValidationError):
        field.clean(pliki)
