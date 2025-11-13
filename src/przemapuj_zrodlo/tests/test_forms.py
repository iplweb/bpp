import pytest
from model_bakery import baker

from przemapuj_zrodlo.forms import PrzemapowaZrodloForm


@pytest.mark.django_db
def test_PrzemapowaZrodloForm_valid():
    """Test poprawnego formularza."""
    zrodlo_z = baker.make("bpp.Zrodlo", nazwa="Źródło A")
    zrodlo_do = baker.make("bpp.Zrodlo", nazwa="Źródło B")

    form = PrzemapowaZrodloForm(
        data={
            "zrodlo_docelowe": zrodlo_do.pk,
            "potwierdzenie": True,
        },
        zrodlo_zrodlowe=zrodlo_z,
    )

    assert form.is_valid()


@pytest.mark.django_db
def test_PrzemapowaZrodloForm_invalid_same_source():
    """Test walidacji - źródło docelowe nie może być tym samym co źródłowe."""
    zrodlo_z = baker.make("bpp.Zrodlo", nazwa="Źródło A")

    form = PrzemapowaZrodloForm(
        data={
            "zrodlo_docelowe": zrodlo_z.pk,
            "potwierdzenie": True,
        },
        zrodlo_zrodlowe=zrodlo_z,
    )

    assert not form.is_valid()
    assert "zrodlo_docelowe" in form.errors


@pytest.mark.django_db
def test_PrzemapowaZrodloForm_invalid_no_confirmation():
    """Test walidacji - brak potwierdzenia."""
    zrodlo_z = baker.make("bpp.Zrodlo", nazwa="Źródło A")
    zrodlo_do = baker.make("bpp.Zrodlo", nazwa="Źródło B")

    form = PrzemapowaZrodloForm(
        data={
            "zrodlo_docelowe": zrodlo_do.pk,
            "potwierdzenie": False,
        },
        zrodlo_zrodlowe=zrodlo_z,
    )

    assert not form.is_valid()
    assert "potwierdzenie" in form.errors
