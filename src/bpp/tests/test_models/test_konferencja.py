# -*- encoding: utf-8 -*-

import pytest

from bpp.models.konferencja import Konferencja


@pytest.mark.django_db
def test_konferencja___str__():
    konf = Konferencja.objects.create(
        nazwa="Konferencja", baza_scopus=True, baza_wos=True, baza_inna="Hej"
    )

    assert str(konf) == "Konferencja [Scopus] [WoS] [Hej]"
