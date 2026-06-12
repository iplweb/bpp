"""Testy wydajnościowe dostępu do ContentType z modelu Rekord.

Rekord.content_type / describe_content_type muszą korzystać z procesowego
cache ContentTypeManager (get_for_id), a nie z gołego .get(pk=...), które
wykonuje realne zapytanie SQL per instancja — kosztowne przy eksportach
multiseek (2 × N zapytań) i listach rekordów.
"""

import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models.cache import Rekord
from bpp.tests.util import any_ciagle


@pytest.mark.django_db
def test_rekord_content_type_korzysta_z_cache(django_assert_num_queries):
    wc = any_ciagle()
    rekord = Rekord.objects.get_original(wc)

    # Rozgrzej procesowy cache ContentTypeManager.
    ContentType.objects.get_for_id(rekord.id[0])

    with django_assert_num_queries(0):
        assert rekord.content_type.model == "wydawnictwo_ciagle"
        assert rekord.describe_content_type


@pytest.mark.django_db
def test_rekord_describe_content_type_wartosc():
    wc = any_ciagle()
    rekord = Rekord.objects.get_original(wc)
    assert str(rekord.describe_content_type) == "wydawnictwo ciągłe"
