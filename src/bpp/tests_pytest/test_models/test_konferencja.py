# -*- encoding: utf-8 -*-

import pytest
from model_mommy import mommy

from bpp.models.konferencja import Konferencja


@pytest.mark.django_db
def test_serialize_konferencja():
    konf = mommy.make(Konferencja)
    ret = konf.eksport_pbn_serializuj()
    assert ret != None