import pytest
from model_bakery import baker

from bpp.models import Rzeczownik


@pytest.mark.django_db
def test_rzeczownik_str():
    rzeczownik = baker.make(
        Rzeczownik, uid="UCZELNIA", m="uczelniaM", d="uczelniD", c="uczelniC"
    )
    expected_str = "Rzeczownik UID=UCZELNIA (uczelniaM, uczelniD, uczelniC, ...)"

    assert str(rzeczownik) == expected_str
