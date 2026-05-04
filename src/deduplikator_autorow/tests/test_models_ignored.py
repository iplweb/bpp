"""Testy modelu IgnoredAuthor (general) i IgnoredScientist (PBN)."""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import IgnoredAuthor, IgnoredScientist


@pytest.mark.django_db
def test_ignored_scientist_can_be_created():
    scientist = baker.make("pbn_api.Scientist")
    user = baker.make("bpp.BppUser")
    obj = IgnoredScientist.objects.create(scientist=scientist, created_by=user)
    assert obj.pk is not None
    assert obj.scientist == scientist


@pytest.mark.django_db
def test_ignored_author_can_be_created():
    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser")
    obj = IgnoredAuthor.objects.create(autor=autor, created_by=user, reason="test")
    assert obj.pk is not None
    assert obj.autor == autor
    assert obj.reason == "test"


@pytest.mark.django_db
def test_ignored_author_one_to_one_constraint():
    """Próba podwójnego dodania tego samego autora rzuca IntegrityError."""
    from django.db import IntegrityError

    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser")
    IgnoredAuthor.objects.create(autor=autor, created_by=user)
    with pytest.raises(IntegrityError):
        IgnoredAuthor.objects.create(autor=autor, created_by=user)
