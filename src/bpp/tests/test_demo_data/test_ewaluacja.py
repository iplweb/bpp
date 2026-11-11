"""Demo data a ewaluacja: rodzaje autorow, punktacja wg rozporzadzenia,
dyscypliny autorow publikacji, cache slotow, liczba N, cleanup."""

import random
from collections import Counter
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection

from bpp.demo_data.default_dyscypliny import seed_default_dyscypliny
from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.dyscypliny import create_autor_dyscypliny
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.punktacja import (
    PROGI_CZASOPISM,
    PROGI_ZWARTE_HST,
    PUNKTY_SPOZA_WYKAZU,
)
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.registry import get_theme
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models.cache import Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny
from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt
from bpp.models.wydawca import Poziom_Wydawcy
from bpp.punktacja_sugestia import PROGI_ZWARTE
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
    LiczbaNDlaUczelni,
)
from ewaluacja_metryki.models import MetrykaAutora

OD_ROKU, DO_ROKU = 2022, 2026


@pytest.mark.django_db
def test_rodzaj_autora_proporcje(tmp_manifest_path):
    """~60% N, ~30% B, ~10% D; jeden rodzaj na autora we wszystkich latach."""
    seed_default_dyscypliny()
    theme = get_theme("realistyczny")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    u = ensure_uczelnia(m, theme=theme)
    kw = dict(theme=theme, manifest=m, batch_size=200, disable_progress=True)
    w = create_wydzialy(n=1, uczelnia=u, rng=random.Random(1), **kw)
    j = create_jednostki(
        per_wydzial=1, wydzialy=w, uczelnia=u, rng=random.Random(2), **kw
    )
    a = create_autorzy(n=400, jednostki=j, rng=random.Random(3), **kw)
    create_autor_dyscypliny(
        autorzy=a,
        lata=range(2022, 2026),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m,
        rng=random.Random(42),
        batch_size=200,
        disable_progress=True,
    )

    rodzaje_autora = {}
    for autor_id, skrot in Autor_Dyscyplina.objects.values_list(
        "autor_id", "rodzaj_autora__skrot"
    ):
        rodzaje_autora.setdefault(autor_id, set()).add(skrot)
    assert all(len(s) == 1 for s in rodzaje_autora.values())

    licznik = Counter(next(iter(s)) for s in rodzaje_autora.values())
    assert set(licznik) == {"N", "B", "D"}
    n = len(rodzaje_autora)
    assert abs(licznik["N"] / n - 0.6) < 0.07
    assert abs(licznik["B"] / n - 0.3) < 0.07
    assert abs(licznik["D"] / n - 0.1) < 0.05
    # Wymiar etatu 1 × 100% → 1 udzial na rok:
    for ad in Autor_Dyscyplina.objects.all()[:20]:
        assert sum(u for _, u in ad.policz_udzialy()) == Decimal(1)


def _create_demo(tmp_path, *extra):
    manifest = tmp_path / "m.json"
    db_name = connection.settings_dict["NAME"]
    call_command(
        "create_demo_data",
        "--wydzialow=1",
        "--jednostek-na-wydzial=2",
        "--autorow=30",
        "--ile-ciaglych=60",
        "--ile-zwartych=40",
        "--zrodel=20",
        "--wydawcow=8",
        f"--od-roku={OD_ROKU}",
        f"--do-roku={DO_ROKU}",
        "--procent-z-dyscyplina=100",
        "--procent-z-subdyscyplina=20",
        "--procent-zmiana-dyscypliny=10",
        "--seed=7",
        f"--manifest-out={manifest}",
        "--batch-size=50",
        "--yes-i-am-sure",
        f"--confirm-db={db_name}",
        *extra,
    )
    return manifest


@pytest.fixture
def demo(db, tmp_path):
    seed_default_dyscypliny()
    return _create_demo(tmp_path)


def test_punkty_artykulow_rowne_punktacji_zrodla(demo):
    punktacja = {
        (z, r): p
        for z, r, p in Punktacja_Zrodla.objects.values_list(
            "zrodlo_id", "rok", "punkty_kbn"
        )
    }
    assert {int(p) for p in punktacja.values()} <= set(PROGI_CZASOPISM)
    assert Dyscyplina_Zrodla.objects.exists()

    for praca in Wydawnictwo_Ciagle.objects.all():
        oczekiwane = punktacja.get((praca.zrodlo_id, praca.rok), PUNKTY_SPOZA_WYKAZU)
        assert praca.punkty_kbn == oczekiwane
        assert praca.charakter_formalny.charakter_ogolny == "art"


def test_punkty_zwartych_wg_progow_wydawcy(demo):
    poziomy = {
        (w, r): p
        for w, r, p in Poziom_Wydawcy.objects.values_list("wydawca_id", "rok", "poziom")
    }
    assert set(poziomy.values()) <= {1, 2}

    rodzaje = Counter()
    for praca in Wydawnictwo_Zwarte.objects.all():
        poziom = poziomy.get((praca.wydawca_id, praca.rok), 0)
        if praca.wydawnictwo_nadrzedne_id is not None:
            rodzaj = "ROZ"
            assert praca.wydawca_id == praca.wydawnictwo_nadrzedne.wydawca_id
            assert praca.rok == praca.wydawnictwo_nadrzedne.rok
        elif praca.autorzy_set.filter(typ_odpowiedzialnosci__skrot="red.").exists():
            rodzaj = "RED"
        else:
            rodzaj = "KS"
        rodzaje[rodzaj] += 1
        assert praca.punkty_kbn in (
            PROGI_ZWARTE[poziom][rodzaj],
            PROGI_ZWARTE_HST[poziom][rodzaj],
        ), (praca, poziom, rodzaj)
    assert rodzaje["KS"] and rodzaje["ROZ"] and rodzaje["RED"]


def test_dyscypliny_autorow_publikacji(demo):
    ad = {
        (a, r): d
        for a, r, d in Autor_Dyscyplina.objects.values_list(
            "autor_id", "rok", "dyscyplina_naukowa_id"
        )
    }
    for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
        qs = model.objects.select_related("rekord")
        assert qs.exclude(dyscyplina_naukowa=None).exists()
        for wa in qs:
            assert wa.dyscyplina_naukowa_id == ad.get((wa.autor_id, wa.rekord.rok))
            assert wa.przypieta


def test_sloty_liczba_n_i_metryki(demo):
    # Kalkulator slotow dopasowuje (prawie) wszystkie prace demo:
    for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
        prace = list(model.objects.all())
        dopasowane = 0
        for praca in prace:
            try:
                ISlot(praca)
                dopasowane += 1
            except CannotAdapt:
                pass
        assert dopasowane / len(prace) > 0.9, model

    assert Cache_Punktacja_Dyscypliny.objects.exists()
    autorzy_z_punktami = (
        Cache_Punktacja_Autora.objects.filter(pkdaut__gt=0)
        .values("autor_id")
        .distinct()
        .count()
    )
    assert autorzy_z_punktami >= 10

    uczelnia = Uczelnia.objects.get()
    okresy = set(
        LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).values_list(
            "okres__rok_od", "okres__rok_do"
        )
    )
    assert okresy == {(2022, 2025), (2026, 2030)}

    # ~1 udzial na autora na rok:
    for u in IloscUdzialowDlaAutoraZaRok.objects.all():
        assert u.ilosc_udzialow == Decimal(1)
    assert IloscUdzialowDlaAutoraZaCalosc.objects.exists()
    assert MetrykaAutora.objects.exists()


@pytest.mark.django_db
def test_bez_ewaluacji(tmp_path):
    seed_default_dyscypliny()
    _create_demo(tmp_path, "--bez-ewaluacji")
    assert Wydawnictwo_Ciagle.objects.exists()
    assert not Cache_Punktacja_Autora.objects.exists()
    assert not LiczbaNDlaUczelni.objects.exists()


def test_cleanup_usuwa_dane_ewaluacji(demo):
    assert Cache_Punktacja_Dyscypliny.objects.exists()
    call_command(
        "cleanup_demo_data",
        f"--manifest={demo}",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )
    assert not Autor.objects.exists()
    for model in (
        Punktacja_Zrodla,
        Dyscyplina_Zrodla,
        Poziom_Wydawcy,
        Cache_Punktacja_Autora,
        Cache_Punktacja_Dyscypliny,
        IloscUdzialowDlaAutoraZaRok,
        IloscUdzialowDlaAutoraZaCalosc,
        MetrykaAutora,
        LiczbaNDlaUczelni,
    ):
        assert not model.objects.exists(), model


@pytest.mark.django_db
def test_cleanup_na_istniejacej_uczelni_przelicza_liczbe_n(tmp_path):
    """Uczelnia sprzed demo przezywa cleanup, a liczba N jest przeliczona
    bez autorow demo (nie zostaja wartosci z danymi demo)."""
    from django.contrib.sites.models import Site

    seed_default_dyscypliny()
    uczelnia = Uczelnia.objects.create(
        nazwa="Istniejąca",
        skrot="IST",
        site=Site.objects.get_or_create(domain="ist.local", defaults={"name": "IST"})[
            0
        ],
    )
    manifest = _create_demo(tmp_path)
    assert LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).exists()

    call_command(
        "cleanup_demo_data",
        f"--manifest={manifest}",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )
    assert Uczelnia.objects.filter(pk=uczelnia.pk).exists()
    assert not LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).exists()
    assert not Punktacja_Zrodla.objects.exists()
    assert not Cache_Punktacja_Dyscypliny.objects.exists()
