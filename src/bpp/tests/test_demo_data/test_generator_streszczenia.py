"""Test generatora streszczeń (Wydawnictwo_*_Streszczenie)."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.streszczenia import create_streszczenia
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import (
    Jezyk,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
)


@pytest.fixture
def prace(transactional_db):
    Jezyk.objects.get_or_create(nazwa="polski", defaults={"skrot": "pol."})
    wc = [baker.make(Wydawnictwo_Ciagle) for _ in range(4)]
    wz = [baker.make(Wydawnictwo_Zwarte) for _ in range(4)]
    return wc, wz


@pytest.mark.django_db(transaction=True)
def test_streszczenia_100_percent(prace, tmp_manifest_path):
    wc, wz = prace
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    create_streszczenia(
        prace_wc=wc,
        prace_wz=wz,
        theme=get_theme("wiedzmin"),
        procent=100,
        manifest=m,
        rng=random.Random(1),
        batch_size=10,
        disable_progress=True,
    )
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 4
    assert Wydawnictwo_Zwarte_Streszczenie.objects.count() == 4
    s = Wydawnictwo_Ciagle_Streszczenie.objects.first()
    assert s.streszczenie  # niepuste
    assert s.jezyk_streszczenia.nazwa == "polski"  # polski znaleziony
    assert m.objects_for("bpp.Wydawnictwo_Ciagle_Streszczenie")


@pytest.mark.django_db(transaction=True)
def test_streszczenia_0_percent(prace, tmp_manifest_path):
    wc, wz = prace
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    create_streszczenia(
        prace_wc=wc,
        prace_wz=wz,
        theme=get_theme("lem"),
        procent=0,
        manifest=m,
        rng=random.Random(1),
        batch_size=10,
        disable_progress=True,
    )
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 0
    assert Wydawnictwo_Zwarte_Streszczenie.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_streszczenia_jezyk_none_when_no_polski(tmp_manifest_path, db):
    # Brak Jezyka 'polski' → fallback None (pole nullable), bez crashu.
    # Baseline test-DB zawiera 'polski' (migracja 0022), więc usuwamy go
    # JAWNIE — inaczej test zależałby od kolejności (flush sąsiednich
    # testów transactional_db) i pękał w izolacji.
    Jezyk.objects.filter(nazwa__icontains="polski").delete()
    wc = [baker.make(Wydawnictwo_Ciagle) for _ in range(2)]
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    create_streszczenia(
        prace_wc=wc,
        prace_wz=[],
        theme=get_theme("realistyczny"),
        procent=100,
        manifest=m,
        rng=random.Random(1),
        batch_size=10,
        disable_progress=True,
    )
    s = Wydawnictwo_Ciagle_Streszczenie.objects.first()
    assert s.jezyk_streszczenia is None
