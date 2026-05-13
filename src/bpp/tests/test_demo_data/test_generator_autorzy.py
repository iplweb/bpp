"""Test generatora Autor + Autor_Jednostka."""

import random

import pytest

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import Autor, Autor_Jednostka


@pytest.fixture
def jednostki_fixture(tmp_manifest_path, db):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    uczelnia = ensure_uczelnia(m)
    w = create_wydzialy(
        n=2,
        uczelnia=uczelnia,
        manifest=m,
        rng=random.Random(1),
        batch_size=10,
        disable_progress=True,
    )
    j = create_jednostki(
        per_wydzial=2,
        wydzialy=w,
        uczelnia=uczelnia,
        manifest=m,
        rng=random.Random(2),
        batch_size=10,
        disable_progress=True,
    )
    return m, j


@pytest.mark.django_db(transaction=True)
def test_create_autorzy_creates_n_records(jednostki_fixture, tmp_manifest_path):
    m, jednostki = jednostki_fixture

    autorzy = create_autorzy(
        n=10,
        jednostki=jednostki,
        manifest=m,
        rng=random.Random(3),
        batch_size=100,
        disable_progress=True,
    )

    assert Autor.objects.count() == 10
    assert len(autorzy) == 10
    assert sorted(m.objects_for("bpp.Autor")) == sorted([a.pk for a in autorzy])


@pytest.mark.django_db(transaction=True)
def test_each_autor_has_one_jednostka(jednostki_fixture, tmp_manifest_path):
    m, jednostki = jednostki_fixture
    autorzy = create_autorzy(
        n=5,
        jednostki=jednostki,
        manifest=m,
        rng=random.Random(3),
        batch_size=100,
        disable_progress=True,
    )

    aj_for = {aj.autor_id: aj for aj in Autor_Jednostka.objects.all()}
    assert len(aj_for) == 5
    for a in autorzy:
        assert a.pk in aj_for
        assert aj_for[a.pk].jednostka_id in {j.pk for j in jednostki}


@pytest.mark.django_db(transaction=True)
def test_autorzy_have_polish_names(jednostki_fixture, tmp_manifest_path):
    from bpp.demo_data.names import IMIONA_POL, NAZWISKA_POL

    m, jednostki = jednostki_fixture
    autorzy = create_autorzy(
        n=5,
        jednostki=jednostki,
        manifest=m,
        rng=random.Random(3),
        batch_size=100,
        disable_progress=True,
    )
    for a in autorzy:
        assert a.imiona in IMIONA_POL
        assert a.nazwisko in NAZWISKA_POL


@pytest.mark.django_db(transaction=True)
def test_no_slug_collision_at_scale(jednostki_fixture, tmp_manifest_path):
    """Birthday-paradox guard: 50 autorow musi miec 50 unikalnych slugow,
    nawet jesli losowe imiona/nazwiska sie powtarzaja."""
    m, jednostki = jednostki_fixture
    autorzy = create_autorzy(
        n=50,
        jednostki=jednostki,
        manifest=m,
        rng=random.Random(7),
        batch_size=100,
        disable_progress=True,
    )
    slugs = list(Autor.objects.values_list("slug", flat=True))
    assert len(slugs) == 50
    assert len(autorzy) == 50
    assert len(set(slugs)) == 50, (
        f"Slug duplicates: {[s for s in slugs if slugs.count(s) > 1]}"
    )


@pytest.mark.django_db(transaction=True)
def test_seed_determinism(jednostki_fixture, tmp_manifest_path):
    m, jednostki = jednostki_fixture
    autorzy_1 = create_autorzy(
        n=5,
        jednostki=jednostki,
        manifest=m,
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    names_1 = [(a.imiona, a.nazwisko) for a in autorzy_1]

    Autor.objects.filter(pk__in=[a.pk for a in autorzy_1]).delete()

    autorzy_2 = create_autorzy(
        n=5,
        jednostki=jednostki,
        manifest=Manifest(path=tmp_manifest_path, database="db", command_args={}),
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    names_2 = [(a.imiona, a.nazwisko) for a in autorzy_2]
    assert names_1 == names_2
