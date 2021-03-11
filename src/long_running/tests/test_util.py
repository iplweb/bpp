import pytest

from bpp.models import Wydawnictwo_Ciagle
from long_running.util import wait_for_object


def test_wait_for_object(wydawnictwo_ciagle):
    with pytest.warns(DeprecationWarning):
        assert (
            wait_for_object(Wydawnictwo_Ciagle, wydawnictwo_ciagle.pk)
            == wydawnictwo_ciagle
        )
