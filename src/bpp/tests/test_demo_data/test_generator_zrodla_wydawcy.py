"""Test generatorow Zrodla + Wydawca."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.wydawcy import create_wydawcy
from bpp.demo_data.generators.zrodla import create_zrodla
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import Rodzaj_Zrodla, Wydawca, Zrodlo


@pytest.fixture
def setup_rodzaje(db):
    for nazwa in ("Czasopismo", "Książka", "Materiały konferencyjne"):
        baker.make(Rodzaj_Zrodla, nazwa=nazwa)


@pytest.mark.django_db(transaction=True)
def test_create_zrodla(setup_rodzaje, tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    zrodla = create_zrodla(
        n=5,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=random.Random(1),
        prefix="Demo — ",
        batch_size=10,
        disable_progress=True,
    )
    assert len(zrodla) == 5
    assert Zrodlo.objects.count() == 5
    for z in zrodla:
        assert z.nazwa.startswith("Demo —")
        assert z.rodzaj_id is not None
        assert any(
            z.nazwa[len("Demo — ") :].startswith(p)
            for p in (
                "Acta",
                "Annales",
                "Folia",
                "Roczniki",
                "Przegląd",
                "Zeszyty Naukowe",
                "Studia",
            )
        )
    assert sorted(m.objects_for("bpp.Zrodlo")) == sorted([z.pk for z in zrodla])


@pytest.mark.django_db(transaction=True)
def test_create_wydawcy(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    wydawcy = create_wydawcy(
        n=3,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=random.Random(1),
        prefix="Demo — ",
        batch_size=10,
        disable_progress=True,
    )
    assert len(wydawcy) == 3
    for w in wydawcy:
        assert w.nazwa.startswith("Demo —")
    assert Wydawca.objects.count() == 3


@pytest.mark.django_db(transaction=True)
def test_zrodla_have_synthetic_issn(setup_rodzaje, tmp_manifest_path):
    import re

    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    zrodla = create_zrodla(
        n=3,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=random.Random(1),
        prefix="Demo — ",
        batch_size=10,
        disable_progress=True,
    )
    for z in zrodla:
        # ISSN format: NNNN-NNNN
        assert re.match(r"^\d{4}-\d{3}[\dX]$", z.issn)


@pytest.mark.django_db(transaction=True)
def test_zrodla_no_slug_collision_at_scale(setup_rodzaje, tmp_manifest_path):
    """AutoSlugField populate_from='nazwa' + bulk_create:
    find_unique() nie widzi instancji ze swojego batcha. Nazwa
    jest unikalna globalnie, wiec slug tez, ale regression guard
    sprawdza ze nic sie nie zepsulo (np. populate_from na inne pole)."""
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    zrodla = create_zrodla(
        n=50,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=random.Random(7),
        prefix="Demo — ",
        batch_size=10,
        disable_progress=True,
    )
    slugs = list(Zrodlo.objects.values_list("slug", flat=True))
    assert len(zrodla) == 50
    assert len(slugs) == 50
    assert len(set(slugs)) == 50, (
        f"Slug duplicates: {[s for s in slugs if slugs.count(s) > 1]}"
    )
