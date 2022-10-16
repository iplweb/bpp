from contextlib import ExitStack as does_not_raise
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kwargs,expectation",
    [
        (
            {"opl_pub_amount": Decimal(10.00), "opl_pub_cost_free": True},
            pytest.raises(ValidationError),
        ),
        (
            {"opl_pub_amount": Decimal(0.00), "opl_pub_cost_free": True},
            does_not_raise(),
        ),
        (
            {"opl_pub_amount": Decimal(10.00), "opl_pub_cost_free": False},
            pytest.raises(ValidationError),
        ),
        (
            {
                "opl_pub_amount": Decimal(10.00),
                "opl_pub_cost_free": False,
                "opl_pub_research_potential": True,
            },
            does_not_raise(),
        ),
        (
            {
                "opl_pub_amount": Decimal(10.00),
                "opl_pub_cost_free": False,
                "opl_pub_research_or_development_projects": True,
            },
            does_not_raise(),
        ),
        (
            {
                "opl_pub_amount": Decimal(10.00),
                "opl_pub_cost_free": False,
                "opl_pub_other": True,
            },
            does_not_raise(),
        ),
        (
            {
                "opl_pub_amount": None,
                "opl_pub_cost_free": False,
                "opl_pub_other": True,
            },
            pytest.raises(ValidationError),
        ),
    ],
)
@pytest.mark.parametrize(
    "obj",
    [
        pytest.lazy_fixture("wydawnictwo_ciagle"),
        pytest.lazy_fixture("wydawnictwo_zwarte"),
        pytest.lazy_fixture("praca_doktorska"),
        pytest.lazy_fixture("praca_habilitacyjna"),
    ],
)
def test_ModelZeZrodlemFinansowania_clean(obj, kwargs, expectation):
    for attr, value in kwargs.items():
        setattr(obj, attr, value)

    with expectation:
        obj.clean()
