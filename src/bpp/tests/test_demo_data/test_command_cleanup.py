"""Integration tests dla `manage.py cleanup_demo_data`.

Roundtrip: create_demo_data → cleanup_demo_data → wszystkie demo
obiekty zniknely, swiadkowie (pre-existing) ocaleli.
"""

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
)


@pytest.fixture
def fixtures_loaded(db):
    """Loaduje minimalny zestaw slownikow dla preflight."""
    for label, _ in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)


@pytest.mark.django_db(transaction=True)
def test_roundtrip_create_then_cleanup(fixtures_loaded, tmp_path):
    """Tworzymy demo, kasujemy, sprawdzamy ze swiadek przezyl."""
    manifest = tmp_path / "m.json"
    db_name = connection.settings_dict["NAME"]

    swiadek = Autor.objects.create(imiona="Swiadek", nazwisko="Test")
    swiadek_pk = swiadek.pk

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
        f"--confirm-db={db_name}",
    )

    assert Jednostka.objects.filter(parent__isnull=True).count() == 1
    # Autor count = swiadek + 3 demo
    assert Autor.objects.count() == 4

    call_command(
        "cleanup_demo_data",
        f"--manifest={manifest}",
        "--yes-i-am-sure",
        f"--confirm-db={db_name}",
    )

    # Demo zniknelo:
    assert Jednostka.objects.count() == 0
    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert Wydawnictwo_Zwarte.objects.count() == 0
    # Swiadek przetrwal:
    assert Autor.objects.filter(pk=swiadek_pk).exists()
    # Zostal tylko swiadek:
    assert Autor.objects.count() == 1
    # Manifest przemianowany:
    assert not manifest.exists()
    applied = list(tmp_path.glob("m.json.applied.*"))
    assert len(applied) == 1


@pytest.mark.django_db(transaction=True)
def test_cleanup_aborts_when_manifest_database_mismatch(fixtures_loaded, tmp_path):
    """Manifest z innej bazy → SystemExit zanim cokolwiek skasujemy."""
    from bpp.demo_data.manifest import Manifest

    db_name = connection.settings_dict["NAME"]

    # Stworz fake manifest dla 'innej' bazy:
    fake_manifest = Manifest(
        path=tmp_path / "fake.json",
        database="zupelnie_inna_baza",
        command_args={},
    )
    fake_manifest.append("bpp.Jednostka", [1, 2, 3])
    fake_manifest.save()

    swiadek = Autor.objects.create(imiona="Swiadek", nazwisko="Test")

    with pytest.raises(SystemExit):
        call_command(
            "cleanup_demo_data",
            f"--manifest={fake_manifest.path}",
            "--yes-i-am-sure",
            f"--confirm-db={db_name}",
        )

    # Nic nie zmienione:
    assert Autor.objects.filter(pk=swiadek.pk).exists()
    assert fake_manifest.path.exists()  # manifest NIE zostal przeniesiony


@pytest.mark.django_db(transaction=True)
def test_cleanup_aborts_wrong_db(fixtures_loaded, tmp_path):
    """Zla nazwa bazy w --confirm-db → SystemExit, manifest NIE
    renamowany, dane NIE usuniete."""
    manifest = tmp_path / "m.json"
    db_name = connection.settings_dict["NAME"]
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
        f"--manifest-out={manifest}",
        "--batch-size=10",
        "--yes-i-am-sure",
        f"--confirm-db={db_name}",
    )
    with pytest.raises(SystemExit):
        call_command(
            "cleanup_demo_data",
            f"--manifest={manifest}",
            "--yes-i-am-sure",
            "--confirm-db=zla",
        )
    assert Jednostka.objects.filter(parent__isnull=True).count() == 1
    assert manifest.exists()  # NIE renamowany
