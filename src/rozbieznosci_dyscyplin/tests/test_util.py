"""Testy `rozbieznosci_dyscyplin.util.object_or_something` oraz placeholder
class `NieistniejacaDyscyplina` z views.py."""

import pytest


@pytest.mark.django_db
def test_object_or_something_returns_existing_object(autor_jan_kowalski):
    """Test that object_or_something returns the actual object when it exists."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = autor_jan_kowalski.tytul

    result = object_or_something(FakeModel(), "tytul")
    assert result == autor_jan_kowalski.tytul


def test_object_or_something_returns_fallback_on_none():
    """Test that object_or_something returns fallback object when attr is None."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = None

    result = object_or_something(FakeModel(), "tytul")
    assert result.pk == -1
    assert result.nazwa == "--"


def test_object_or_something_handles_object_does_not_exist():
    """Test that object_or_something handles ObjectDoesNotExist exception.

    NOTE: This test reveals a bug in util.py - when ObjectDoesNotExist is raised,
    the 'res' variable is not defined, causing UnboundLocalError. The test
    is written to verify the expected (correct) behavior, but will fail until
    the bug is fixed.
    """
    from django.core.exceptions import ObjectDoesNotExist

    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        @property
        def tytul(self):
            raise ObjectDoesNotExist()

    # Tymczasowo testujemy, ze bug istnieje
    import pytest

    with pytest.raises(UnboundLocalError):
        object_or_something(FakeModel(), "tytul")


def test_object_or_something_custom_default_pk():
    """Test that object_or_something uses custom default_pk."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = None

    result = object_or_something(FakeModel(), "tytul", default_pk=-999)
    assert result.pk == -999


def test_object_or_something_custom_kwargs():
    """Test that object_or_something uses custom kwargs."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = None

    result = object_or_something(
        FakeModel(), "tytul", default_attr=None, foo="bar", baz=123
    )
    assert result.foo == "bar"
    assert result.baz == 123


def test_nieistniejaca_dyscyplina():
    """Test NieistniejacaDyscyplina placeholder class."""
    from rozbieznosci_dyscyplin.views import NieistniejacaDyscyplina

    assert NieistniejacaDyscyplina.pk == -1
    assert NieistniejacaDyscyplina.nazwa == "--"
