# -*- encoding: utf-8 -*-

import pytest
from django.utils import timezone
from model_mommy import mommy

from bpp.models.konferencja import Konferencja


@pytest.mark.django_db
def test_Konferencja_eksport_pbn_serializuj():
    konf = mommy.make(
        Konferencja,
        nazwa="Lel",
        skrocona_nazwa="foo",
        rozpoczecie=timezone.now(),
        zakonczenie=timezone.now(),
        miasto="foo",
        panstwo="bar",
        baza_scopus=True,
        baza_wos=True,
        baza_inna="Quux")

    res = konf.eksport_pbn_serializuj()

    assert res.find("name").text == "Lel"
    assert res.find("web-of-science-indexed").text == "true"
    assert res.find("scopus-indexed").text == "true"
    assert res.find("other-indexes").text == "Quux"


@pytest.mark.django_db
def test_konferencja___str__():
    konf = Konferencja.objects.create(
        nazwa="Konferencja", baza_scopus=True, baza_wos=True, baza_inna="Hej")

    assert str(konf) == "Konferencja [Scopus] [WoS] [Hej]"
