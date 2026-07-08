"""Repro: Crossref_Mapper dla typów książkowych musi mieć
``jest_wydawnictwem_zwartym=True``.

Bug: ``_get_crossref_mapper`` (helpers.py) tworzył mapper przez
``get_or_create`` bez ``defaults=``, więc świeży wiersz dla ``book-chapter``
dostawał modelowy default ``False`` — ptaszek „jest wydawnictwem zwartym"
w kroku weryfikacji importera się nie zaznaczał. Migracja 0409 robiła tylko
``.update()`` na istniejących wierszach, których w chwili migracji nie było.

Naprawa: (1) migracja 0467 seeduje komplet 16 wierszy z właściwą wartością,
(2) leniwe ``get_or_create`` dostaje ``defaults=`` — na wypadek typu dodanego
w przyszłości bez seeda.
"""

import pytest

from bpp.models import Crossref_Mapper


@pytest.mark.django_db
def test_migracja_zaseedowala_wszystkie_typy():
    """Migracja 0467 utworzyła 16 wierszy z poprawnym jest_wydawnictwem_zwartym."""
    C = Crossref_Mapper.CHARAKTER_CROSSREF
    assert Crossref_Mapper.objects.count() == len(C.values)

    book = Crossref_Mapper.objects.get(charakter_crossref=C.BOOK_CHAPTER)
    assert book.jest_wydawnictwem_zwartym is True

    article = Crossref_Mapper.objects.get(charakter_crossref=C.JOURNAL_ARTICLE)
    assert article.jest_wydawnictwem_zwartym is False


@pytest.mark.django_db
def test_lazy_mapper_book_chapter_jest_wydawnictwem_zwartym():
    """Typ nie-zaseedowany (usunięty) tworzony leniwie → True dla book-chapter."""
    from importer_publikacji.views import _get_crossref_mapper

    # Symuluj typ jeszcze nie-zaseedowany (np. dodany w przyszłości).
    Crossref_Mapper.objects.filter(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK_CHAPTER
    ).delete()

    mapper = _get_crossref_mapper("book-chapter")

    assert mapper is not None
    assert mapper.jest_wydawnictwem_zwartym is True


@pytest.mark.django_db
def test_lazy_mapper_journal_article_nie_jest_zwartym():
    """Typ nie-zaseedowany (usunięty) tworzony leniwie → False dla artykułu."""
    from importer_publikacji.views import _get_crossref_mapper

    Crossref_Mapper.objects.filter(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.JOURNAL_ARTICLE
    ).delete()

    mapper = _get_crossref_mapper("journal-article")

    assert mapper is not None
    assert mapper.jest_wydawnictwem_zwartym is False


@pytest.mark.django_db
def test_lazy_mapper_nie_nadpisuje_istniejacego():
    """Istniejący wiersz (np. ręcznie zmieniony w adminie) nie jest nadpisany."""
    from importer_publikacji.views import _get_crossref_mapper

    # Admin ręcznie odznaczył ptaszek dla book-chapter — get_or_create
    # z defaults= NIE może tego nadpisać.
    Crossref_Mapper.objects.filter(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK_CHAPTER
    ).update(jest_wydawnictwem_zwartym=False)

    mapper = _get_crossref_mapper("book-chapter")

    assert mapper.jest_wydawnictwem_zwartym is False


def test_default_helper_book_types():
    """Statyczny helper zwraca poprawną wartość dla typów książkowych."""
    C = Crossref_Mapper.CHARAKTER_CROSSREF
    assert Crossref_Mapper.default_jest_wydawnictwem_zwartym(C.BOOK_CHAPTER) is True
    assert Crossref_Mapper.default_jest_wydawnictwem_zwartym(C.BOOK) is True
    assert Crossref_Mapper.default_jest_wydawnictwem_zwartym(C.MONOGRAPH) is True
    assert Crossref_Mapper.default_jest_wydawnictwem_zwartym(C.JOURNAL_ARTICLE) is False
    assert Crossref_Mapper.default_jest_wydawnictwem_zwartym(C.PROCEEDINGS) is False
