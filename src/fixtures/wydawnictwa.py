import pytest

from bpp.models import Wydawnictwo_Zwarte


@pytest.fixture
def wydawnictwo_nadrzedne(wydawnictwo_zwarte):
    """Zwraca nowe wydawnictwo, bedace nadrzednym dla domyslnej fikstury wydawnictwa zwartego."""
    # Lazy import baker — patrz fixtures/pbn_api.py po pelne uzasadnienie.
    # TL;DR: model_bakery wola apps.is_installed() w czasie importu, co
    # psuje preload conftesta przez pytest-testcontainers-django.
    from model_bakery import baker

    wn = baker.make(Wydawnictwo_Zwarte)
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_id = wn.pk
    wydawnictwo_zwarte.save(update_fields=["wydawnictwo_nadrzedne_id"])
    return wn
