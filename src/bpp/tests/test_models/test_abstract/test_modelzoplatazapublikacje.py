from contextlib import ExitStack as does_not_raise
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError


@pytest.fixture(
    params=[
        "wydawnictwo_ciagle",
        "wydawnictwo_zwarte",
        "praca_doktorska",
        "praca_habilitacyjna",
    ]
)
def opl_pub_obj(request):
    return request.getfixturevalue(request.param)


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
def test_ModelZeZrodlemFinansowania_clean(opl_pub_obj, kwargs, expectation):
    for attr, value in kwargs.items():
        setattr(opl_pub_obj, attr, value)

    with expectation:
        opl_pub_obj.clean()
