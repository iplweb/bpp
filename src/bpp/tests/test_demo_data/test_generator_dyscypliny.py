"""Test generatora Autor_Dyscyplina."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.dyscypliny import create_autor_dyscypliny
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import Autor_Dyscyplina, Dyscyplina_Naukowa


@pytest.fixture
def setup(tmp_manifest_path, db):
    # Stworz kilka dyscyplin
    for i in range(5):
        baker.make(Dyscyplina_Naukowa, nazwa=f"Dysc{i}", kod=f"D{i}")

    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    u = ensure_uczelnia(m)
    w = create_wydzialy(
        n=1,
        uczelnia=u,
        manifest=m,
        rng=random.Random(1),
        batch_size=10,
        disable_progress=True,
    )
    j = create_jednostki(
        per_wydzial=1,
        wydzialy=w,
        uczelnia=u,
        manifest=m,
        rng=random.Random(2),
        batch_size=10,
        disable_progress=True,
    )
    a = create_autorzy(
        n=20,
        jednostki=j,
        manifest=m,
        rng=random.Random(3),
        batch_size=10,
        disable_progress=True,
    )
    return m, a


@pytest.mark.django_db(transaction=True)
def test_100_percent_full_coverage(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(2017, 2026),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m,
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    # 20 autorow * 9 lat = 180 rekordow
    assert Autor_Dyscyplina.objects.count() == 20 * 9
    # Kazdy ma dyscypline, nikt nie ma subdyscypliny:
    assert (
        Autor_Dyscyplina.objects.filter(dyscyplina_naukowa__isnull=False).count() == 180
    )
    assert (
        Autor_Dyscyplina.objects.filter(subdyscyplina_naukowa__isnull=False).count()
        == 0
    )


@pytest.mark.django_db(transaction=True)
def test_50_percent_coverage(setup):
    m, autorzy = setup  # 20 autorow
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(2017, 2026),
        procent_z_dyscyplina=50,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m,
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    autorzy_z_dysc = Autor_Dyscyplina.objects.values("autor_id").distinct().count()
    # Powinno byc okolo 10 (50% z 20), ale moze sie wahac.
    assert 5 <= autorzy_z_dysc <= 15


@pytest.mark.django_db(transaction=True)
def test_subdyscyplina_assigned(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(2017, 2020),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=100,
        procent_zmiana_dyscypliny=0,
        manifest=m,
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    # Wszyscy z subdyscyplina (rozna od dyscypliny):
    assert (
        Autor_Dyscyplina.objects.filter(subdyscyplina_naukowa__isnull=False).count()
        == Autor_Dyscyplina.objects.count()
    )


@pytest.mark.django_db(transaction=True)
def test_zmiana_dyscypliny_w_2022(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(2017, 2026),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=100,  # wszyscy zmieniaja
        manifest=m,
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    # Dla kazdego autora: dyscyplina w 2017–2021 != dyscyplina w 2022–2025
    for autor in autorzy:
        d_przed = Autor_Dyscyplina.objects.filter(autor=autor, rok=2017).first()
        d_po = Autor_Dyscyplina.objects.filter(autor=autor, rok=2022).first()
        if d_przed and d_po:
            assert d_przed.dyscyplina_naukowa_id != d_po.dyscyplina_naukowa_id


@pytest.mark.django_db(transaction=True)
def test_manifest_pks_match(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(2017, 2020),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m,
        rng=random.Random(99),
        batch_size=100,
        disable_progress=True,
    )
    assert sorted(m.objects_for("bpp.Autor_Dyscyplina")) == sorted(
        Autor_Dyscyplina.objects.values_list("pk", flat=True)
    )
