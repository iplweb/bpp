"""Generator Uczelni (singleton) dla demo_data."""

from __future__ import annotations

from bpp.demo_data.manifest import Manifest
from bpp.models import Uczelnia


def ensure_uczelnia(manifest: Manifest) -> Uczelnia:
    """Zwraca singleton Uczelni. Jesli brak — tworzy 'Demo —' i wpisuje do
    manifestu z flaga `created_by_demo`."""
    existing = Uczelnia.objects.first()
    if existing is not None:
        return existing

    uczelnia = Uczelnia.objects.create(
        nazwa="Demo — Uczelnia Testowa",
        skrot="DEMO",
        nazwa_dopelniacz_field="Demo — Uczelni Testowej",
    )
    manifest.append("bpp.Uczelnia", [uczelnia.pk], extra={"created_by_demo": True})
    return uczelnia
