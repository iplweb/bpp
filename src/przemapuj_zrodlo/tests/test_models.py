import pytest
from model_bakery import baker

from przemapuj_zrodlo.models import PrzemapowaZrodla


@pytest.mark.django_db
def test_PrzemapowaZrodla_creation(admin_user):
    """Test utworzenia przemapowania."""
    zrodlo_z = baker.make("bpp.Zrodlo", nazwa="Źródło A")
    zrodlo_do = baker.make("bpp.Zrodlo", nazwa="Źródło B")

    przemapowanie = PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo_z,
        zrodlo_do=zrodlo_do,
        liczba_publikacji=10,
        publikacje_historia=[
            {"id": 1, "tytul": "Test 1", "rok": 2020},
            {"id": 2, "tytul": "Test 2", "rok": 2021},
        ],
        utworzono_przez=admin_user,
    )

    assert przemapowanie.zrodlo_z == zrodlo_z
    assert przemapowanie.zrodlo_do == zrodlo_do
    assert przemapowanie.liczba_publikacji == 10
    assert len(przemapowanie.publikacje_historia) == 2
    assert przemapowanie.utworzono_przez == admin_user


@pytest.mark.django_db
def test_PrzemapowaZrodla_str(admin_user):
    """Test reprezentacji tekstowej przemapowania."""
    zrodlo_z = baker.make("bpp.Zrodlo", nazwa="Źródło A")
    zrodlo_do = baker.make("bpp.Zrodlo", nazwa="Źródło B")

    przemapowanie = PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo_z,
        zrodlo_do=zrodlo_do,
        liczba_publikacji=5,
        utworzono_przez=admin_user,
    )

    string_repr = str(przemapowanie)
    assert "Źródło A" in string_repr
    assert "Źródło B" in string_repr
    assert "5 pub." in string_repr


@pytest.mark.django_db
def test_PrzemapowaZrodla_jest_cofniete(admin_user):
    """Test właściwości jest_cofniete."""
    zrodlo_z = baker.make("bpp.Zrodlo")
    zrodlo_do = baker.make("bpp.Zrodlo")

    przemapowanie = PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo_z,
        zrodlo_do=zrodlo_do,
        liczba_publikacji=3,
        utworzono_przez=admin_user,
    )

    assert not przemapowanie.jest_cofniete
    assert przemapowanie.mozna_cofnac


@pytest.mark.django_db
def test_PrzemapowaZrodla_cofniete(admin_user):
    """Test przemapowania cofniętego."""
    from django.utils import timezone

    zrodlo_z = baker.make("bpp.Zrodlo")
    zrodlo_do = baker.make("bpp.Zrodlo")

    przemapowanie = PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo_z,
        zrodlo_do=zrodlo_do,
        liczba_publikacji=3,
        utworzono_przez=admin_user,
        cofnieto=timezone.now(),
        cofnieto_przez=admin_user,
    )

    assert przemapowanie.jest_cofniete
    assert not przemapowanie.mozna_cofnac
