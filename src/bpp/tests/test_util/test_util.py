import pytest
from model_bakery import baker

from bpp.models import Autor
from bpp.util import get_copy_from_db, has_changed, slugify_function


def test_slugify_function():
    test = "Waldemar A. Łącki,,()*':;\r\n[]"
    result = "Waldemar-A-Lacki"
    assert slugify_function(test) == result


def test_slugify_function_double_dash():
    test = "Andrzej   Wróbel"
    result = "Andrzej-Wrobel"
    assert slugify_function(test) == result


@pytest.mark.django_db
def test_get_copy_from_db():
    a = baker.make(Autor)
    b = get_copy_from_db(a)
    assert a.pk == b.pk


@pytest.mark.django_db
def test_has_changed():
    a = baker.make(Autor)
    assert has_changed(a, "nazwisko") is False

    a.nazwisko = "Foo"
    assert has_changed(a, "nazwisko") is True

    a.save()
    assert has_changed(a, ["nazwisko", "imiona"]) is False

    a.imiona = "Bar"
    assert has_changed(a, ["nazwisko", "imiona"]) is True
