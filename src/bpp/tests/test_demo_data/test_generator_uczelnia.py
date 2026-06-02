"""Test generatora Uczelni (singleton)."""

import pytest
from model_bakery import baker

from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import Uczelnia


@pytest.mark.django_db
def test_creates_uczelnia_when_missing(tmp_manifest_path):
    assert not Uczelnia.objects.exists()
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    uczelnia = ensure_uczelnia(m, theme=get_theme("realistyczny"), prefix="Demo — ")

    assert Uczelnia.objects.count() == 1
    assert uczelnia.nazwa.startswith("Demo")
    assert m.objects_for("bpp.Uczelnia") == [uczelnia.pk]
    assert m.extra_for("bpp.Uczelnia").get("created_by_demo") is True


@pytest.mark.django_db
def test_reuses_existing_uczelnia(tmp_manifest_path):
    existing = baker.make(Uczelnia, nazwa="Istniejaca", skrot="IST")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    uczelnia = ensure_uczelnia(m, theme=get_theme("realistyczny"), prefix="Demo — ")

    assert uczelnia.pk == existing.pk
    assert Uczelnia.objects.count() == 1
    assert m.objects_for("bpp.Uczelnia") == []
