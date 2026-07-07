"""E2E smoke: srednia skala — 2 wydz., 3 jedn., 20 aut., 30 prac."""

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydzial,
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
def test_e2e_medium_scale(fixtures_loaded, tmp_path):
    """E2E srednia skala: 2 wydz × 3 jedn × 20 aut × 30 WC × 30 WZ × 3 lata."""
    manifest = tmp_path / "m.json"
    db_name = connection.settings_dict["NAME"]
    call_command(
        "create_demo_data",
        "--wydzialow=2",
        "--jednostek-na-wydzial=3",
        "--autorow=20",
        "--ile-ciaglych=30",
        "--ile-zwartych=30",
        "--zrodel=10",
        "--wydawcow=5",
        "--od-roku=2020",
        "--do-roku=2022",
        "--procent-z-dyscyplina=100",
        "--procent-z-subdyscyplina=30",
        "--procent-zmiana-dyscypliny=20",
        "--seed=42",
        f"--manifest-out={manifest}",
        "--batch-size=10",
        "--yes-i-am-sure",
        f"--confirm-db={db_name}",
    )
    assert Wydzial.objects.count() == 2
    # Faza B (#438): jednostki wiszą pod węzłami-lustrami wydziałów (1 lustro
    # na wydział) → 6 realnych + 2 węzły-lustra.
    assert Jednostka.objects.count() == 8
    assert Jednostka.objects.filter(legacy_wydzial_id__isnull=True).count() == 6
    assert Autor.objects.count() == 20
    # 100% z dyscyplina, 3 lata, 20 autorow → 60 rekordow dyscyplin
    assert Autor_Dyscyplina.objects.count() == 60
    assert Wydawnictwo_Ciagle.objects.count() == 30
    # WZ count >= 30 because of nadrzedne (procent_rozdzialy=20 default,
    # n_rozdzialow=6, n_nadrzednych=max(1, 6//5)=1, total=31)
    assert Wydawnictwo_Zwarte.objects.count() >= 30
    # Powiazania (kazda praca 1–8 autorow → min 60, max 480)
    assert Wydawnictwo_Ciagle_Autor.objects.count() >= 30
    assert Wydawnictwo_Zwarte_Autor.objects.count() >= 30
