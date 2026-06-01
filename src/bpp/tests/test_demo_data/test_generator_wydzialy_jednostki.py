"""Testy generatorow Wydzialow i Jednostek."""

import pytest
from model_bakery import baker

from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import Jednostka, Uczelnia, Wydzial


@pytest.mark.django_db(transaction=True)
def test_create_wydzialy_creates_n_records(tmp_manifest_path, rng):
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=3,
        uczelnia=uczelnia,
        manifest=m,
        rng=rng,
        disable_progress=True,
    )

    assert len(wydzialy) == 3
    assert Wydzial.objects.count() == 3
    for w in wydzialy:
        assert w.uczelnia_id == uczelnia.pk
        assert w.nazwa.startswith("Demo")
    assert sorted(m.objects_for("bpp.Wydzial")) == sorted(w.pk for w in wydzialy)


@pytest.mark.django_db(transaction=True)
def test_create_jednostki_per_wydzial(tmp_manifest_path, rng):
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=2,
        uczelnia=uczelnia,
        manifest=m,
        rng=rng,
        disable_progress=True,
    )
    jednostki = create_jednostki(
        per_wydzial=3,
        wydzialy=wydzialy,
        uczelnia=uczelnia,
        manifest=m,
        rng=rng,
        disable_progress=True,
    )

    assert len(jednostki) == 6
    assert Jednostka.objects.filter(pk__in=[j.pk for j in jednostki]).count() == 6
    wydzial_pks = {w.pk for w in wydzialy}
    for j in jednostki:
        assert j.uczelnia_id == uczelnia.pk
        assert j.wydzial_id in wydzial_pks
    assert sorted(m.objects_for("bpp.Jednostka")) == sorted(j.pk for j in jednostki)


@pytest.mark.django_db(transaction=True)
def test_jednostki_mptt_rebuild_called(tmp_manifest_path, rng):
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=2,
        uczelnia=uczelnia,
        manifest=m,
        rng=rng,
        disable_progress=True,
    )
    create_jednostki(
        per_wydzial=2,
        wydzialy=wydzialy,
        uczelnia=uczelnia,
        manifest=m,
        rng=rng,
        disable_progress=True,
    )

    for j in Jednostka.objects.filter(uczelnia=uczelnia):
        assert j.lft > 0
        assert j.rght > j.lft
