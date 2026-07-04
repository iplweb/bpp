"""Generator Uczelni (singleton) dla demo_data."""

from __future__ import annotations

from django.contrib.sites.models import Site

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix
from bpp.models import Uczelnia


def ensure_uczelnia(manifest: Manifest, *, theme: Theme, prefix: str = "") -> Uczelnia:
    """Zwraca singleton Uczelni. Jesli brak — tworzy z nazwa motywu i wpisuje
    do manifestu z flaga `created_by_demo`.

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

    nazwa = apply_prefix(theme.uczelnia_nazwy[0], prefix)
    uczelnia = Uczelnia.objects.create(
        nazwa=nazwa,
        skrot=theme.uczelnia_skrot,
        nazwa_dopelniacz_field=nazwa,
        site=site,
    )
    manifest.append("bpp.Uczelnia", [uczelnia.pk], extra={"created_by_demo": True})
    return uczelnia
