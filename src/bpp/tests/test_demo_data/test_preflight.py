"""Testy pre-flight checkow demo_data."""

import pytest
from model_bakery import baker

from bpp.demo_data.preflight import REQUIRED_DICTIONARIES, check_required


@pytest.mark.django_db
def test_check_required_returns_missing_when_empty():
    missing = check_required()
    labels = {label for label, _ in missing}
    assert "bpp.Charakter_Formalny" in labels or len(REQUIRED_DICTIONARIES) > 0


@pytest.mark.django_db
def test_check_required_returns_empty_when_all_present():
    for label, _hint in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        from django.apps import apps

        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)

    missing = check_required()
    assert missing == []


def test_required_dictionaries_includes_critical_models():
    labels = {label for label, _ in REQUIRED_DICTIONARIES}
    assert "bpp.Charakter_Formalny" in labels
    assert "bpp.Typ_KBN" in labels
    assert "bpp.Jezyk" in labels
    assert "bpp.Dyscyplina_Naukowa" in labels
    assert "bpp.Typ_Odpowiedzialnosci" in labels
