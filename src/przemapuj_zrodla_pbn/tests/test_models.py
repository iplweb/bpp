import pytest
from model_bakery import baker

from przemapuj_zrodla_pbn.models import PrzeMapowanieZrodla


@pytest.mark.django_db
def test_przemapowanie_zrodla_creation(django_user_model):
    """Test podstawowego utworzenia obiektu PrzeMapowanieZrodla"""
    user = baker.make(django_user_model)
    journal_skasowane = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_stare = baker.make("bpp.Zrodlo", pbn_uid=journal_skasowane)
    zrodlo_nowe = baker.make("bpp.Zrodlo")

    przemapowanie = PrzeMapowanieZrodla.objects.create(
        zrodlo_skasowane_pbn_uid=journal_skasowane,
        zrodlo_stare=zrodlo_stare,
        zrodlo_nowe=zrodlo_nowe,
        liczba_rekordow=5,
        utworzono_przez=user,
        rekordy_historia=[
            {"tytul": "Testowa publikacja", "rok": 2023},
        ],
    )

    assert przemapowanie.pk is not None
    assert przemapowanie.liczba_rekordow == 5
    assert przemapowanie.utworzono_przez == user
    assert len(przemapowanie.rekordy_historia) == 1
    assert przemapowanie.rekordy_historia[0]["tytul"] == "Testowa publikacja"


@pytest.mark.django_db
def test_przemapowanie_zrodla_str_representation(django_user_model):
    """Test reprezentacji tekstowej obiektu PrzeMapowanieZrodla"""
    user = baker.make(django_user_model)
    journal_skasowane = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara Gazeta", pbn_uid=journal_skasowane
    )
    zrodlo_nowe = baker.make("bpp.Zrodlo", nazwa="Nowa Gazeta")

    przemapowanie = baker.make(
        PrzeMapowanieZrodla,
        zrodlo_skasowane_pbn_uid=journal_skasowane,
        zrodlo_stare=zrodlo_stare,
        zrodlo_nowe=zrodlo_nowe,
        utworzono_przez=user,
    )

    str_representation = str(przemapowanie)
    assert "Stara Gazeta" in str_representation
    assert "Nowa Gazeta" in str_representation


@pytest.mark.django_db
def test_przemapowanie_zrodla_default_rekordy_historia(django_user_model):
    """Test domyślnej wartości pola rekordy_historia"""
    user = baker.make(django_user_model)
    journal_skasowane = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_stare = baker.make("bpp.Zrodlo", pbn_uid=journal_skasowane)
    zrodlo_nowe = baker.make("bpp.Zrodlo")

    przemapowanie = baker.make(
        PrzeMapowanieZrodla,
        zrodlo_skasowane_pbn_uid=journal_skasowane,
        zrodlo_stare=zrodlo_stare,
        zrodlo_nowe=zrodlo_nowe,
        utworzono_przez=user,
    )

    assert przemapowanie.rekordy_historia == []
