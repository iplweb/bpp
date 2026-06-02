"""Test generatora Wydawnictwo_Ciagle + Wydawnictwo_Ciagle_Autor."""

import random
import re

import pytest
from model_bakery import baker

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydawnictwa_ciagle import create_wc
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.generators.zrodla import create_zrodla
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Rodzaj_Zrodla,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)


@pytest.fixture
def slowniki(db):
    # Niektore slowniki (Charakter_Formalny, Jezyk) maja juz baseline z
    # migracji 0035 — uzywamy lookup po skrocie, zeby nie kolidowac z
    # istniejacymi rekordami (skrot jest unique). nazwa moze sie roznic.
    Charakter_Formalny.objects.get_or_create(skrot="AC", defaults={"nazwa": "Artykuł"})
    Charakter_Formalny.objects.get_or_create(
        skrot="DEMO_PA", defaults={"nazwa": "Praca poglądowa"}
    )
    Typ_KBN.objects.get_or_create(skrot="PO", defaults={"nazwa": "Praca oryginalna"})
    Jezyk.objects.get_or_create(skrot="pol.", defaults={"nazwa": "polski"})
    Status_Korekty.objects.get_or_create(nazwa="Po korekcie")
    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )
    baker.make(Rodzaj_Zrodla, nazwa="Czasopismo")


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
    z = create_zrodla(
        n=3,
        theme=theme,
        manifest=m,
        rng=random.Random(4),
        batch_size=10,
        disable_progress=True,
    )
    return m, a, z, theme


@pytest.mark.django_db(transaction=True)
def test_creates_n_prac(setup):
    m, autorzy, zrodla, theme = setup
    prace = create_wc(
        n=20,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        batch_size=10,
        disable_progress=True,
    )
    assert Wydawnictwo_Ciagle.objects.count() == 20
    assert len(prace) == 20


@pytest.mark.django_db(transaction=True)
def test_each_praca_has_authors(setup):
    m, autorzy, zrodla, theme = setup
    create_wc(
        n=10,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        batch_size=10,
        disable_progress=True,
    )
    for praca in Wydawnictwo_Ciagle.objects.all():
        count = Wydawnictwo_Ciagle_Autor.objects.filter(rekord=praca).count()
        assert 1 <= count <= 8


@pytest.mark.django_db(transaction=True)
def test_doi_format(setup):
    m, autorzy, zrodla, theme = setup
    create_wc(
        n=5,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        batch_size=10,
        disable_progress=True,
    )
    pattern = re.compile(r"^10\.\d{4}/demo\.\d{4}\.\d+$")
    for praca in Wydawnictwo_Ciagle.objects.all():
        assert pattern.match(praca.doi)


@pytest.mark.django_db(transaction=True)
def test_pbn_uid_always_empty(setup):
    m, autorzy, zrodla, theme = setup
    create_wc(
        n=5,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        batch_size=10,
        disable_progress=True,
    )
    for praca in Wydawnictwo_Ciagle.objects.all():
        assert praca.pbn_uid_id is None


@pytest.mark.django_db(transaction=True)
def test_lata_w_zakresie(setup):
    m, autorzy, zrodla, theme = setup
    create_wc(
        n=20,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(2018, 2021),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        batch_size=10,
        disable_progress=True,
    )
    lata_w_bazie = set(Wydawnictwo_Ciagle.objects.values_list("rok", flat=True))
    assert lata_w_bazie.issubset({2018, 2019, 2020})


@pytest.mark.django_db(transaction=True)
def test_manifest_includes_powiazania(setup):
    m, autorzy, zrodla, theme = setup
    create_wc(
        n=5,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(2020, 2023),
        theme=theme,
        manifest=m,
        rng=random.Random(99),
        batch_size=10,
        disable_progress=True,
    )
    assert len(m.objects_for("bpp.Wydawnictwo_Ciagle")) == 5
    assert len(m.objects_for("bpp.Wydawnictwo_Ciagle_Autor")) >= 5
