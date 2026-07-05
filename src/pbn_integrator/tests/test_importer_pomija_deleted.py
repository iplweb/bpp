"""Import PBN → BPP musi POMIJAĆ prace usunięte w PBN (``status == DELETED``).

Geneza: importer publikacji (w odróżnieniu od integracji konferencji/źródeł,
które jawnie robią ``.exclude(status="DELETED")``) NIE sprawdzał statusu lustra
``pbn_api.Publication``. Skutek: praca usunięta po stronie PBN materializowała
się jako świeży ``Wydawnictwo_Ciagle``/``Wydawnictwo_Zwarte`` po stronie BPP.

Te testy pilnują dwóch ścieżek tworzących rekord:
- ``importuj_publikacje_po_pbn_uid_id`` — choke point (również import
  pojedynczej pracy po UID),
- ``importuj_publikacje_instytucji`` — batch po całym lustrze.
"""

import pytest
from model_bakery import baker

from bpp.models import Rekord, Wydawnictwo_Ciagle
from pbn_api.models import Publication
from pbn_integrator import importer

ARTICLE_OBJECT = {
    "type": "ARTICLE",
    "title": "Praca usunięta w PBN",
    "year": 2023,
}


def _make_publication(mongo_id, status):
    return baker.make(
        Publication,
        mongoId=mongo_id,
        versions=[{"current": True, "object": dict(ARTICLE_OBJECT)}],
        status=status,
    )


@pytest.mark.django_db
def test_importuj_po_uid_pomija_deleted():
    """Import pojedynczej pracy DELETED nie tworzy rekordu BPP (zwraca None)."""
    _make_publication("d1", "DELETED")

    # client=None jest bezpieczne: guard musi odrzucić DELETED zanim
    # cokolwiek sięgnie do klienta PBN.
    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "d1",
        client=None,
        default_jednostka=None,
    )

    assert ret is None
    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert Rekord.objects.filter(pbn_uid_id="d1").count() == 0


@pytest.mark.django_db
def test_importuj_publikacje_instytucji_nie_dispatchuje_deleted(monkeypatch):
    """Batch po lustrze pomija prace DELETED — dispatch dostaje tylko ACTIVE."""
    from bpp.models import Dyscyplina_Naukowa, Rodzaj_Zrodla  # noqa: F401

    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")

    _make_publication("a1", "ACTIVE")
    _make_publication("d1", "DELETED")

    dispatched = []
    monkeypatch.setattr(
        importer,
        "importuj_publikacje_po_pbn_uid_id",
        lambda mongoId, **kwargs: dispatched.append(mongoId),
    )

    importer.importuj_publikacje_instytucji(client=None, default_jednostka=None)

    assert "a1" in dispatched
    assert "d1" not in dispatched
