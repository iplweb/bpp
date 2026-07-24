"""Testy generatorow Wydzialow i Jednostek."""

import pytest
from model_bakery import baker

from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import Jednostka, Uczelnia


@pytest.mark.django_db(transaction=True)
def test_create_wydzialy_creates_n_records(tmp_manifest_path, rng):
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=3,
        uczelnia=uczelnia,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )

    # Faza C (#438): „wydział" = jednostka top-level (parent IS NULL).
    assert len(wydzialy) == 3
    assert Jednostka.objects.filter(parent__isnull=True).count() == 3
    for w in wydzialy:
        assert w.parent_id is None
        assert w.uczelnia_id == uczelnia.pk
        assert w.nazwa.startswith("Demo")
        assert "Wydział" in w.nazwa
    assert sorted(m.objects_for("bpp.Jednostka")) == sorted(w.pk for w in wydzialy)


@pytest.mark.django_db(transaction=True)
def test_create_wydzialy_wiecej_niz_pula_zachowuje_unikalne_nazwy(
    tmp_manifest_path, rng
):
    """Regresja: n > len(theme.wydzial_dziedziny) nie może naruszyć unique
    constraintu na nazwie jednostki.

    Dawniej ``wydzial_nazwy`` cyklowało pulę dziedzin bez deduplikacji, więc
    dla motywu z małą pulą (wiedzmin/harry-potter mają 6 dziedzin) i domyślnej
    liczby wydziałów (10) ``bulk_create`` wywalał się na kluczu unikalnym
    nazwy (podwójna wartość klucza). Faza C (#438): wydziały to jednostki
    TOP-LEVEL, więc constraintem jest ``bpp_jednostka_nazwa_key``."""
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=10,
        uczelnia=uczelnia,
        theme=get_theme("wiedzmin"),  # 6 dziedzin < 10 → cykl puli
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )

    assert len(wydzialy) == 10
    assert Jednostka.objects.filter(parent__isnull=True).count() == 10
    # Wszystkie nazwy unikalne — inaczej bulk_create by nie przeszedł.
    assert len({w.nazwa for w in wydzialy}) == 10


@pytest.mark.django_db(transaction=True)
def test_create_jednostki_per_wydzial(tmp_manifest_path, rng):
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=2,
        uczelnia=uczelnia,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )
    jednostki = create_jednostki(
        per_wydzial=3,
        wydzialy=wydzialy,
        uczelnia=uczelnia,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )

    assert len(jednostki) == 6
    assert Jednostka.objects.filter(pk__in=[j.pk for j in jednostki]).count() == 6
    # Faza C (#438): ``wydzial`` (denorm self-FK) = root-Jednostka (dawny
    # wydział), więc dzieci wskazują wprost na pk rootów.
    wezel_pks = {w.pk for w in wydzialy}
    for j in jednostki:
        assert j.uczelnia_id == uczelnia.pk
        assert j.wydzial_id in wezel_pks
        # marker + realistyczny prefiks jednostki, NIE "Jednostka N"
        assert j.nazwa.startswith("Demo — ")
        from bpp.demo_data.themes.base import SHARED_JEDNOSTKA_PREFIKSY

        bez_markera = j.nazwa[len("Demo — ") :]
        assert any(bez_markera.startswith(p) for p in SHARED_JEDNOSTKA_PREFIKSY)
        assert "Jednostka " not in j.nazwa
    # Manifest bpp.Jednostka = rooty (z create_wydzialy) + dzieci.
    assert sorted(m.objects_for("bpp.Jednostka")) == sorted(
        [w.pk for w in wydzialy] + [j.pk for j in jednostki]
    )


@pytest.mark.django_db(transaction=True)
def test_create_jednostki_wiecej_niz_pula_zachowuje_unikalne_nazwy(
    tmp_manifest_path, rng
):
    """Regresja: liczba jednostek > iloczyn (prefiksy × dziedziny) nie może
    naruszyć unique constraintu ``Jednostka.nazwa``.

    ``compose_jednostka_nazwa`` losuje ``prefiks × dziedzina`` bez deduplikacji,
    więc gdy jednostek jest więcej niż kombinacji (wiedzmin: 7 prefiksów × 8
    dziedzin = 56), ``bulk_create`` wywalał się na ``bpp_jednostka_nazwa_key``."""
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    theme = get_theme("wiedzmin")  # 7 prefiksów × 8 dziedzin = 56 kombinacji

    wydzialy = create_wydzialy(
        n=3,
        uczelnia=uczelnia,
        theme=theme,
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )
    # 3 wydz × 25 = 75 jednostek > 56 kombinacji → wymusza sufiksowanie.
    jednostki = create_jednostki(
        per_wydzial=25,
        wydzialy=wydzialy,
        uczelnia=uczelnia,
        theme=theme,
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )

    assert len(jednostki) == 75
    assert len({j.nazwa for j in jednostki}) == 75  # wszystkie unikalne


@pytest.mark.django_db(transaction=True)
def test_jednostki_mptt_rebuild_called(tmp_manifest_path, rng):
    uczelnia = baker.make(Uczelnia, nazwa="Demo — Uczelnia", skrot="DEMO")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    wydzialy = create_wydzialy(
        n=2,
        uczelnia=uczelnia,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )
    create_jednostki(
        per_wydzial=2,
        wydzialy=wydzialy,
        uczelnia=uczelnia,
        theme=get_theme("realistyczny"),
        manifest=m,
        rng=rng,
        prefix="Demo — ",
        disable_progress=True,
    )

    for j in Jednostka.objects.filter(uczelnia=uczelnia):
        assert j.lft > 0
        assert j.rght > j.lft
