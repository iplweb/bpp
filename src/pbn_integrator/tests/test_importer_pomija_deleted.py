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

from bpp.models import Autor, Rekord, Wydawca, Wydawnictwo_Ciagle
from pbn_api.models import Publication, Publisher, Scientist
from pbn_integrator import importer
from pbn_integrator.utils.scientists import integruj_autorow_z_uczelni

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


# --- Wydawcy: hurtowy import nie tworzy Wydawca dla DELETED bez odpowiednika ---


def _make_publisher(mongo_id, status):
    return baker.make(
        Publisher,
        mongoId=mongo_id,
        publisherName=f"Wydawnictwo {mongo_id}",
        mniswId=123,
        versions=[{"current": True, "object": {"points": {}}}],
        status=status,
    )


@pytest.mark.django_db
def test_importuj_wydawce_pomija_deleted_bez_odpowiednika():
    """DELETED wydawca bez odpowiednika w BPP nie tworzy nowego Wydawca."""
    publisher = _make_publisher("p_del", "DELETED")

    ret = importer.importuj_jednego_wydawce(publisher)

    assert not ret
    assert Wydawca.objects.filter(pbn_uid=publisher).count() == 0


@pytest.mark.django_db
def test_importuj_wydawce_tworzy_active():
    """Kontrola: ACTIVE wydawca nadal jest tworzony (guard jest status-specific)."""
    publisher = _make_publisher("p_act", "ACTIVE")

    importer.importuj_jednego_wydawce(publisher)

    assert Wydawca.objects.filter(pbn_uid=publisher).count() == 1


# --- Autorzy z uczelni: import_unexistent nie tworzy Autor dla DELETED ---


def _make_scientist(mongo_id, status):
    return baker.make(
        Scientist,
        mongoId=mongo_id,
        versions=[
            {"current": True, "object": {"name": "Jan", "lastName": f"Nowak{mongo_id}"}}
        ],
        status=status,
        from_institution_api=True,
    )


@pytest.mark.django_db
def test_integruj_autorow_pomija_deleted_bez_odpowiednika():
    """DELETED naukowiec bez dopasowania w BPP nie tworzy nowego Autora."""
    _make_scientist("s_del", "DELETED")

    integruj_autorow_z_uczelni(client=None, instutition_id=None, import_unexistent=True)

    assert Autor.objects.filter(pbn_uid_id="s_del").count() == 0


@pytest.mark.django_db
def test_integruj_autorow_tworzy_active():
    """Kontrola: ACTIVE naukowiec bez dopasowania nadal jest tworzony."""
    _make_scientist("s_act", "ACTIVE")

    integruj_autorow_z_uczelni(client=None, instutition_id=None, import_unexistent=True)

    assert Autor.objects.filter(pbn_uid_id="s_act").count() == 1
