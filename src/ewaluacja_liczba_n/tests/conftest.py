import pytest


@pytest.fixture
def rodzaj_autora_n(db):
    """Fixture dla rodzaju autora N (pracownik naukowy w liczbie N)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults=dict(
            nazwa="pracownik naukowy w liczbie N",
            jest_w_n=True,
            licz_sloty=True,
            sort=1,
        ),
    )
    return obj


@pytest.fixture
def rodzaj_autora_d(db):
    """Fixture dla rodzaju autora D (doktorant)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="D",
        defaults=dict(nazwa="doktorant", jest_w_n=False, licz_sloty=True, sort=3),
    )
    return obj


@pytest.fixture
def rodzaj_autora_b(db):
    """Fixture dla rodzaju autora B (pracownik badawczy spoza N)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="B",
        defaults=dict(
            nazwa="pracownik badawczy spoza N", jest_w_n=False, licz_sloty=True, sort=2
        ),
    )
    return obj


@pytest.fixture
def rodzaj_autora_z(db):
    """Fixture dla rodzaju autora Z (inny zatrudniony, nie naukowy)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="Z",
        defaults=dict(
            nazwa="inny zatrudniony, nie naukowy", jest_w_n=False, licz_sloty=False
        ),
    )
    return obj
