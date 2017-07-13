# -*- encoding: utf-8 -*-

import pytest
from django.utils import timezone
from model_mommy import mommy

from bpp.models.konferencja import Konferencja


@pytest.mark.django_db
def test_serialize_konferencja():
    konf = mommy.make(Konferencja)
    ret = konf.eksport_pbn_serializuj()
    assert ret != None

    konf = mommy.make(
        Konferencja,
        skrocona_nazwa="foo",
        rozpoczecie=timezone.now(),
        zakonczenie=timezone.now(),
        miasto="foo",
        panstwo="bar")
    ret = konf.eksport_pbn_serializuj()
    assert ret != None
