# -*- encoding: utf-8 -*-


import pytest


@pytest.mark.django_db
@pytest.mark.parametrize(
    "informacje,expected",
    [("bez sensu", None), ("2016 vol. 5 nr 10", "5"), ("2019 Bd 4 nr. 3 test", "4")],
)
def test_eksport_pbn_get_volume(informacje, expected, wydawnictwo_ciagle):
    wydawnictwo_ciagle.informacje = informacje
    assert wydawnictwo_ciagle.numer_tomu() == expected


@pytest.mark.django_db
def test_eksport_pbn_volume(wydawnictwo_ciagle):
    wydawnictwo_ciagle.informacje = "bez sensu"
    assert wydawnictwo_ciagle.numer_tomu() is None

    wydawnictwo_ciagle.informacje = "2016 vol 4"
    assert wydawnictwo_ciagle.numer_tomu() == "4"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "informacje,expected",
    [
        ("bez sensu", None),
        ("2016 vol. 5 nr 10", "10"),
        ("2019 Bd 4 nr. 3 test", "3 test"),
        ("2019 Bd 4 nr 3 test", "3 test"),
        ("2019 Bd 4 z. 3 test", "3 test"),
        ("2019 Bd 4 h. 3 test", "3 test"),
        ("2019 Bd 4 iss. 311 test", "311 test"),
    ],
)
def test_eksport_pbn_get_issue(informacje, expected, wydawnictwo_ciagle):
    wydawnictwo_ciagle.informacje = informacje
    assert wydawnictwo_ciagle.numer_wydania() == expected


def test_punktacja_zrodla(wydawnictwo_ciagle):
    assert wydawnictwo_ciagle.punktacja_zrodla() is None

    z = wydawnictwo_ciagle.zrodlo
    z.punktacja_zrodla_set.create(rok=1990, impact_factor=100)

    assert wydawnictwo_ciagle.punktacja_zrodla() is None

    z.punktacja_zrodla_set.create(rok=wydawnictwo_ciagle.rok, impact_factor=37)
    assert wydawnictwo_ciagle.punktacja_zrodla().impact_factor == 37
