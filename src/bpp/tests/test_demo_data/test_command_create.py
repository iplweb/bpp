"""Integration tests dla `manage.py create_demo_data`."""

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
)


@pytest.fixture
def fixtures_loaded(db):
    """Loaduje minimalny zestaw slownikow dla preflight.

    Uzywa get_or_create / exists()-guard, zeby nie kolidowac z baseline
    danymi wgrywanymi przez migracje (np. Charakter_Formalny, Jezyk).
    """
    for label, _ in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)


@pytest.mark.django_db(transaction=True)
def test_command_smoke_minimal(fixtures_loaded, tmp_path):
    """Minimalny end-to-end: 1 wydz / 1 jedn / 3 aut / 3 WC / 3 WZ."""
    manifest = tmp_path / "m.json"
    call_command(
        "create_demo_data",
        "--wydzialow=1",
        "--jednostek-na-wydzial=1",
        "--autorow=3",
        "--ile-ciaglych=3",
        "--ile-zwartych=3",
        "--zrodel=2",
        "--wydawcow=2",
        "--seed=1",
        f"--manifest-out={manifest}",
        "--batch-size=10",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )

    assert manifest.exists()
    assert Wydzial.objects.count() == 1
    assert Jednostka.objects.count() == 1
    assert Autor.objects.count() == 3
    assert Wydawnictwo_Ciagle.objects.count() == 3
    # WZ tworzy + potencjalne nadrzedne, stad >=
    assert Wydawnictwo_Zwarte.objects.count() >= 3


@pytest.mark.django_db(transaction=True)
def test_command_preflight_fails_when_no_dyscyplina():
    """Preflight musi zlapac brak Dyscyplin_Naukowych ZANIM cokolwiek
    stworzy."""
    # Tworzymy slowniki BEZ dyscyplin
    for label, _ in REQUIRED_DICTIONARIES:
        if label == "bpp.Dyscyplina_Naukowa":
            continue
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)

    with pytest.raises(SystemExit):
        call_command(
            "create_demo_data",
            "--wydzialow=1",
            "--jednostek-na-wydzial=1",
            "--autorow=1",
            "--ile-ciaglych=1",
            "--ile-zwartych=1",
            "--zrodel=1",
            "--wydawcow=1",
            "--seed=1",
            "--yes-i-am-sure",
            f"--confirm-db={connection.settings_dict['NAME']}",
        )
    assert Wydzial.objects.count() == 0  # nic nie stworzone


@pytest.mark.django_db(transaction=True)
def test_command_aborts_without_flags_non_tty(fixtures_loaded, tmp_path):
    """Bez --yes-i-am-sure i bez TTY → SystemExit (pytest stdin non-tty)."""
    with pytest.raises(SystemExit):
        call_command(
            "create_demo_data",
            "--wydzialow=1",
            "--jednostek-na-wydzial=1",
            "--autorow=1",
            "--ile-ciaglych=1",
            "--ile-zwartych=1",
            "--zrodel=1",
            "--wydawcow=1",
            "--seed=1",
        )
    assert Wydzial.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_command_aborts_wrong_db_name(fixtures_loaded):
    """--confirm-db != rzeczywista nazwa bazy → SystemExit."""
    with pytest.raises(SystemExit):
        call_command(
            "create_demo_data",
            "--wydzialow=1",
            "--jednostek-na-wydzial=1",
            "--autorow=1",
            "--ile-ciaglych=1",
            "--ile-zwartych=1",
            "--zrodel=1",
            "--wydawcow=1",
            "--seed=1",
            "--yes-i-am-sure",
            "--confirm-db=zla_nazwa",
        )
    assert Wydzial.objects.count() == 0
