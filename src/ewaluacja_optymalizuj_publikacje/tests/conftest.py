import pytest


@pytest.fixture
def okres_2022(db):
    """Okres 2022–2025 — metryki w testach muszą być z okresu, do którego
    należy rok publikacji (widok czyta metryki tylko z tego okresu)."""
    from ewaluacja_common.models import OkresEwaluacji

    return OkresEwaluacji.objects.get_or_create(rok_od=2022, defaults={"rok_do": 2025})[
        0
    ]


@pytest.fixture
def okres_2026(db):
    from ewaluacja_common.models import OkresEwaluacji

    return OkresEwaluacji.objects.get_or_create(rok_od=2026, defaults={"rok_do": 2030})[
        0
    ]
