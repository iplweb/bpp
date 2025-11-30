"""
Fixtures for deduplikator_autorow tests.
"""

import pytest
from model_bakery import baker

from pbn_api.models import OsobaZInstytucji, Scientist


@pytest.fixture
def glowny_autor(autor_maker, tytuly):
    """Główny autor z pełnymi danymi"""
    return autor_maker(imiona="Jan Marian", nazwisko="Gal-Cisoń", tytul="dr hab.")


@pytest.fixture
def scientist_for_glowny_autor(glowny_autor):
    """Scientist powiązany z głównym autorem"""
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    return scientist


@pytest.fixture
def osoba_z_instytucji(scientist_for_glowny_autor):
    """OsobaZInstytucji powiązana z głównym autorem"""
    return baker.make(OsobaZInstytucji, personId=scientist_for_glowny_autor)
