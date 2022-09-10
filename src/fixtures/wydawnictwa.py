import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Zwarte


@pytest.fixture
def wydawnictwo_nadrzedne(wydawnictwo_zwarte):
    """Zwraca nowe wydawnictwo, bedace nadrzednym dla domyslnej fikstury wydawnictwa zwartego."""
    wn = baker.make(Wydawnictwo_Zwarte)
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_id = wn.pk
    wydawnictwo_zwarte.save(update_fields=["wydawnictwo_nadrzedne_id"])
    return wn
