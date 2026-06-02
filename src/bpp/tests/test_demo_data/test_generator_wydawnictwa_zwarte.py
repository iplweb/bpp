"""Test generatora Wydawnictwo_Zwarte + nadrzedne + powiazania."""

import random
import re

import pytest

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydawcy import create_wydawcy
from bpp.demo_data.generators.wydawnictwa_zwarte import create_wz
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Zwarte,
)


@pytest.fixture
def slowniki(db):
    # Baseline migracji 0035 ladujac fixtures (charakter_formalny.json,
    # jezyk.json, status_korekty.json) — wiec uzywamy get_or_create po
    # unikalnym kluczu (skrot/nazwa) zeby nie kolidowac. Typ_KBN i
    # Typ_Odpowiedzialnosci NIE sa w baseline (komentarze w 0035.py
    # wskazuja ze sa ladowane pozniej / przez migracje 0067).
    Charakter_Formalny.objects.get_or_create(skrot="KS", defaults={"nazwa": "Książka"})
    Charakter_Formalny.objects.get_or_create(
        skrot="ROZ", defaults={"nazwa": "Rozdział książki"}
    )
    Typ_KBN.objects.get_or_create(skrot="PO", defaults={"nazwa": "Praca oryginalna"})
    Jezyk.objects.get_or_create(skrot="pol.", defaults={"nazwa": "polski"})
    Status_Korekty.objects.get_or_create(nazwa="Po korekcie")
    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )


@pytest.fixture
def setup(slowniki, tmp_manifest_path):
    theme = get_theme("realistyczny")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    u = ensure_uczelnia(m, theme=theme)
    w = create_wydzialy(
        n=1,
        uczelnia=u,
        theme=theme,
        manifest=m,
        rng=random.Random(1),
        batch_size=10,
        disable_progress=True,
    )
    j = create_jednostki(
        per_wydzial=1,
        wydzialy=w,
        uczelnia=u,
        theme=theme,
        manifest=m,
        rng=random.Random(2),
        batch_size=10,
        disable_progress=True,
    )
    a = create_autorzy(
        n=10,
        jednostki=j,
        theme=theme,
        manifest=m,
        rng=random.Random(3),
        batch_size=10,
        disable_progress=True,
    )
    wyd = create_wydawcy(
        n=3,
        theme=theme,
        manifest=m,
        rng=random.Random(4),
        batch_size=10,
        disable_progress=True,
    )
    return m, a, wyd, theme


@pytest.mark.django_db(transaction=True)
def test_creates_n_prac(setup):
    m, autorzy, wydawcy, theme = setup
    prace = create_wz(
        n=20,
        autorzy=autorzy,
        wydawcy=wydawcy,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        procent_rozdzialy=0,
        batch_size=10,
        disable_progress=True,
    )
    assert Wydawnictwo_Zwarte.objects.count() == 20
    assert len(prace) == 20


@pytest.mark.django_db(transaction=True)
def test_doi_format(setup):
    m, autorzy, wydawcy, theme = setup
    create_wz(
        n=5,
        autorzy=autorzy,
        wydawcy=wydawcy,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        procent_rozdzialy=0,
        batch_size=10,
        disable_progress=True,
    )
    pattern = re.compile(r"^10\.\d{4}/demo\.\d{4}\.\d+$")
    for praca in Wydawnictwo_Zwarte.objects.all():
        assert pattern.match(praca.doi)


@pytest.mark.django_db(transaction=True)
def test_rozdzialy_have_nadrzedne(setup):
    m, autorzy, wydawcy, theme = setup
    create_wz(
        n=10,
        autorzy=autorzy,
        wydawcy=wydawcy,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        procent_rozdzialy=100,
        batch_size=10,
        disable_progress=True,
    )
    # Wszystkie zwykle prace sa rozdzialami → wszystkie maja
    # wydawnictwo_nadrzedne.
    rozdzialy = Wydawnictwo_Zwarte.objects.filter(wydawnictwo_nadrzedne__isnull=False)
    assert rozdzialy.count() == 10
    # Plus nadrzedne (osobne ksiazki) — przynajmniej 1.
    nadrzedne = Wydawnictwo_Zwarte.objects.filter(wydawnictwo_nadrzedne__isnull=True)
    assert nadrzedne.count() >= 1


@pytest.mark.django_db(transaction=True)
def test_procent_rozdzialy_validates_range(setup):
    m, autorzy, wydawcy, theme = setup
    for invalid in (-1, 101, 150):
        with pytest.raises(ValueError, match="procent_rozdzialy"):
            create_wz(
                n=5,
                autorzy=autorzy,
                wydawcy=wydawcy,
                lata=range(2020, 2022),
                theme=theme,
                manifest=m,
                rng=random.Random(1),
                procent_rozdzialy=invalid,
                batch_size=10,
                disable_progress=True,
            )


@pytest.mark.django_db(transaction=True)
def test_pbn_uid_zawsze_puste(setup):
    m, autorzy, wydawcy, theme = setup
    create_wz(
        n=5,
        autorzy=autorzy,
        wydawcy=wydawcy,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        procent_rozdzialy=20,
        batch_size=10,
        disable_progress=True,
    )
    for praca in Wydawnictwo_Zwarte.objects.all():
        assert praca.pbn_uid_id is None
