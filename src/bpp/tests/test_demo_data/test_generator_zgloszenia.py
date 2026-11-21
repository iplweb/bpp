"""Testy generatora zgłoszeń publikacji (zglos_publikacje) w danych demo."""

import json
import random

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.demo_data.generators.zgloszenia import (
    STATUSY_PODPIETE,
    WAGI_STATUSOW,
    rozklad_statusow,
)
from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import Autor, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor

Statusy = Zgloszenie_Publikacji.Statusy


@pytest.fixture
def fixtures_loaded(db):
    for label, _ in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)


def _create(manifest, *extra):
    call_command(
        "create_demo_data",
        "--wydzialow=1",
        "--jednostek-na-wydzial=2",
        "--autorow=8",
        "--ile-ciaglych=6",
        "--ile-zwartych=6",
        "--zrodel=2",
        "--wydawcow=2",
        "--seed=7",
        "--bez-ewaluacji",
        f"--manifest-out={manifest}",
        "--batch-size=10",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
        *extra,
    )


def _cleanup(manifest):
    call_command(
        "cleanup_demo_data",
        f"--manifest={manifest}",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )


def _snapshot():
    return sorted(
        Zgloszenie_Publikacji.objects.values_list(
            "status",
            "tytul_oryginalny",
            "rodzaj_zglaszanej_publikacji",
            "email",
            "strona_www",
            "doi",
        )
    )


def test_rozklad_statusow_pokrywa_wszystkie_statusy():
    wynik = rozklad_statusow(40, random.Random(1))
    assert len(wynik) == 40
    assert set(wynik) == set(WAGI_STATUSOW)


def test_rozklad_statusow_male_n():
    assert len(rozklad_statusow(3, random.Random(1))) == 3
    assert rozklad_statusow(0, random.Random(1)) == []


@pytest.mark.django_db
def test_create_demo_data_tworzy_zgloszenia(fixtures_loaded, tmp_path):
    manifest = tmp_path / "m.json"
    _create(manifest, "--zgloszen=21")

    zgloszenia = list(Zgloszenie_Publikacji.objects.all())
    assert len(zgloszenia) == 21
    assert {z.status for z in zgloszenia} == set(WAGI_STATUSOW)
    assert all(z.tytul_oryginalny.startswith("Demo — ") for z in zgloszenia)

    for z in zgloszenia:
        if z.status in STATUSY_PODPIETE:
            praca = z.odpowiednik_w_bpp
            assert isinstance(praca, Wydawnictwo_Ciagle | Wydawnictwo_Zwarte)
            assert z.tytul_oryginalny == praca.tytul_oryginalny
            assert z.rok == praca.rok
        else:
            assert z.object_id is None
        if z.status == Statusy.WYMAGA_ZMIAN:
            assert z.przyczyna_zwrotu
            assert z.kod_do_edycji is not None
        if z.status == Statusy.ZAIMPORTOWANY:
            assert z.zaimportowano is not None
        if z.status != Statusy.SPAM:
            assert z.zgloszenie_publikacji_autor_set.exists()
        assert z.utworzono <= z.ostatnio_zmieniony
        z.clean()  # opłaty spójne z walidacją modelu

    # Podpięte zgłoszenia wskazują RÓŻNE prace:
    podpiete = [
        (z.content_type_id, z.object_id)
        for z in zgloszenia
        if z.status in STATUSY_PODPIETE
    ]
    assert len(podpiete) == len(set(podpiete))
    assert any(z.strona_www for z in zgloszenia)

    data = json.loads(manifest.read_text())["objects"]
    assert sorted(data["zglos_publikacje.Zgloszenie_Publikacji"]["pks"]) == sorted(
        z.pk for z in zgloszenia
    )
    assert sorted(data["zglos_publikacje.Zgloszenie_Publikacji_Autor"]["pks"]) == (
        sorted(Zgloszenie_Publikacji_Autor.objects.values_list("pk", flat=True))
    )


@pytest.mark.django_db
def test_cleanup_usuwa_zgloszenia_i_seed_jest_deterministyczny(
    fixtures_loaded, tmp_path
):
    manifest = tmp_path / "m.json"
    _create(manifest, "--zgloszen=15")
    pierwszy = _snapshot()
    assert len(pierwszy) == 15

    _cleanup(manifest)
    assert Zgloszenie_Publikacji.global_objects.count() == 0
    assert Zgloszenie_Publikacji_Autor.objects.count() == 0
    assert Autor.objects.count() == 0

    manifest2 = tmp_path / "m2.json"
    _create(manifest2, "--zgloszen=15")
    assert _snapshot() == pierwszy


@pytest.mark.django_db
def test_zgloszen_zero_i_bez_prefiksu(fixtures_loaded, tmp_path):
    _create(tmp_path / "a.json", "--zgloszen=0")
    assert Zgloszenie_Publikacji.objects.count() == 0

    _cleanup(tmp_path / "a.json")
    _create(tmp_path / "b.json", "--zgloszen=10", "--bez-prefiksu")
    assert Zgloszenie_Publikacji.objects.count() == 10
    assert not Zgloszenie_Publikacji.objects.filter(
        tytul_oryginalny__startswith="Demo"
    ).exists()
