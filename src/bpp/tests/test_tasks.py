from unittest.mock import Mock

import pytest

from bpp.models import Wydawnictwo_Ciagle
from bpp.tasks import _zaktualizuj_liczbe_cytowan


@pytest.mark.django_db
def test_zaktualizuj_liczbe_cytowan(uczelnia, wydawnictwo_ciagle, mocker):

    m = Mock()
    m.query_multiple = Mock(
        return_value=[{wydawnictwo_ciagle.pk: {"timesCited": "31337"}}]
    )

    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    _zaktualizuj_liczbe_cytowan(
        [
            Wydawnictwo_Ciagle,
        ]
    )

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 31337
