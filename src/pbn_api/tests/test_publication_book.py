"""Testy property ``Publication.book`` / ``Publication.book_title``.

Gdy rozdział zaimportowano z PBN, jego rodzic (książka) siedzi w surowym
JSON-ie publikacji pod ``object.book``. Szablon opisu bibliograficznego nie
umie wywołać ``value_or_none("object", "book", "title")`` (brak argumentów w
wywołaniach szablonowych), więc wystawiamy wartość przez property — analogicznie
do istniejącego ``Publication.journal``.
"""

import pytest
from model_bakery import baker

from pbn_api.models import Publication


def _publikacja(object_dict):
    return baker.make(
        Publication,
        versions=[{"current": True, "object": object_dict}],
    )


@pytest.mark.django_db
def test_book_zwraca_slownik_rodzica():
    pub = _publikacja({"book": {"title": "Monografia z PBN", "year": 2020}})
    assert pub.book == {"title": "Monografia z PBN", "year": 2020}


@pytest.mark.django_db
def test_book_title_zwraca_tytul_rodzica():
    pub = _publikacja({"book": {"title": "Monografia z PBN"}})
    assert pub.book_title == "Monografia z PBN"


@pytest.mark.django_db
def test_book_brak_book_zwraca_none():
    pub = _publikacja({"title": "Rozdział bez rodzica"})
    assert pub.book is None
    assert pub.book_title is None


@pytest.mark.django_db
def test_book_title_book_bez_title_zwraca_none():
    pub = _publikacja({"book": {"year": 2020}})
    assert pub.book_title is None
