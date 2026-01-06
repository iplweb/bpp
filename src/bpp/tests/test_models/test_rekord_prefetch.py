"""Test dla prefetch_related slów kluczowych z Rekord."""

import pytest
from model_bakery import baker

from bpp.models.cache import Rekord
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_rekord_prefetch_slowa_kluczowe():
    """Test ze prefetch_related dla slow kluczowych dziala poprawnie z Rekord."""
    # Utwórz wydawnictwo ze slowami kluczowymi
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test publikacja")
    wc.slowa_kluczowe.add("slowo1", "slowo2", "slowo3")

    # Pobierz rekord z prefetch
    rekord = Rekord.objects.prefetch_related("slowa_kluczowe").first()

    # Sprawdz ze slowa kluczowe sa poprawnie pobrane
    # slowa_kluczowe zwraca obiekty SlowaKluczoweView z polem tag.name
    slowa = list(rekord.slowa_kluczowe.all())
    assert len(slowa) == 3
    nazwy = {s.tag.name for s in slowa}
    assert nazwy == {"slowo1", "slowo2", "slowo3"}
