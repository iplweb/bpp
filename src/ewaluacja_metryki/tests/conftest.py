import pytest

from ewaluacja_common.okres import KLUCZ_SESJI


def _okres(rok_od, rok_do):
    # get_or_create: okresy seeduje migracja, ale teardown TransactionTestCase
    # potrafi je zmieść — nie polegamy na ich obecności.
    from ewaluacja_common.models import OkresEwaluacji

    okres, _ = OkresEwaluacji.objects.get_or_create(
        rok_od=rok_od, defaults={"rok_do": rok_do}
    )
    return okres


@pytest.fixture
def okres_2022(db):
    return _okres(2022, 2025)


@pytest.fixture
def okres_2026(db):
    return _okres(2026, 2030)


def wybierz_okres(client, okres):
    """Ustaw w sesji klienta testowego okres wybrany w górnej belce."""
    session = client.session
    session[KLUCZ_SESJI] = okres.pk
    session.save()
