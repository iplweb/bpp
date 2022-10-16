import pytest

from pbn_api.tests.utils import middleware

from django.contrib.messages import get_messages

from bpp.admin.helpers import sprobuj_policzyc_sloty
from bpp.const import PBN_MAX_ROK, PBN_MIN_ROK


@pytest.mark.django_db
def test_sprobuj_policzyc_sloty(rf, zwarte_z_dyscyplinami):
    req = rf.get("/")
    for a in range(PBN_MIN_ROK, PBN_MAX_ROK + 1):
        zwarte_z_dyscyplinami.rok = a
        zwarte_z_dyscyplinami.save()

        with middleware(req):
            sprobuj_policzyc_sloty(req, zwarte_z_dyscyplinami)

        msg = get_messages(req)
        assert (
            'Wydawnictwo Zwarte ĄćłłóńŹ</a>" będą mogły być obliczone.'
            in list(msg)[0].message
        )
