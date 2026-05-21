"""Generator Uczelni (singleton) dla demo_data."""

from __future__ import annotations

from django.contrib.sites.models import Site

from bpp.demo_data.manifest import Manifest
from bpp.models import Uczelnia


def ensure_uczelnia(manifest: Manifest) -> Uczelnia:
    """Zwraca singleton Uczelni. Jesli brak — tworzy 'Demo —' i wpisuje do
    manifestu z flaga `created_by_demo`.

    Multi-host: Uczelnia.site jest NOT NULL (migracja 0417). W kontekście
    CLI/demo bierzemy pierwszy Site (default 'example.com' z django.contrib.sites
    fixture) — jeśli brak, tworzymy 'demo.local'.
    """
    existing = Uczelnia.objects.first()
    if existing is not None:
        return existing

    site = Site.objects.first()
    if site is None:
        site = Site.objects.create(domain="demo.local", name="Demo")

    uczelnia = Uczelnia.objects.create(
        nazwa="Demo — Uczelnia Testowa",
        skrot="DEMO",
        nazwa_dopelniacz_field="Demo — Uczelni Testowej",
        site=site,
    )
    manifest.append("bpp.Uczelnia", [uczelnia.pk], extra={"created_by_demo": True})
    return uczelnia
