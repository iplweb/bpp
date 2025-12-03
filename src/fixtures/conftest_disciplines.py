"""PBN discipline fixtures."""

from uuid import uuid4

import pytest

from pbn_api.models import Discipline


def _dyscyplina_maker(nazwa, kod, dyscyplina_pbn):
    """Produkuje dyscypliny naukowe WRAZ z odpowiednim wpisem tłumacza
    dyscyplin"""
    from bpp.models import Dyscyplina_Naukowa
    from pbn_api.models import TlumaczDyscyplin

    d = Dyscyplina_Naukowa.objects.get_or_create(nazwa=nazwa, kod=kod)[0]
    TlumaczDyscyplin.objects.get_or_create(
        dyscyplina_w_bpp=d,
        pbn_2017_2021=dyscyplina_pbn,
        pbn_2022_2023=dyscyplina_pbn,
        pbn_2024_now=dyscyplina_pbn,
    )
    return d


@pytest.fixture
def pbn_dyscyplina1_hst(db, pbn_discipline_group):
    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        uuid=uuid4(),
        code="701",
        name="nauka teologiczna",
        scientificFieldName="Dziedzina nauk teologicznych",
    )[0]


@pytest.fixture
def pbn_dyscyplina2_hst(db, pbn_discipline_group):
    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        uuid=uuid4(),
        code="101",
        name="nauka humanistyczna",
        scientificFieldName="Dziedzina nauk humanistycznych",
    )[0]


@pytest.fixture
def dyscyplina2_hst(db, pbn_dyscyplina2_hst):
    return _dyscyplina_maker(
        nazwa="nauka humanistyczna", kod="1.1", dyscyplina_pbn=pbn_dyscyplina2_hst
    )


@pytest.fixture
def pbn_dyscyplina3(db, pbn_discipline_group):
    return Discipline.objects.get_or_create(
        parent_group=pbn_discipline_group,
        uuid=uuid4(),
        code="403",
        name="trzecia dyscyplina",
        scientificFieldName="Dziedzina trzecich dyscyplin",
    )[0]


@pytest.fixture
def dyscyplina3(db, pbn_dyscyplina3):
    return _dyscyplina_maker(
        nazwa="trzecia dyscyplina", kod="4.3", dyscyplina_pbn=pbn_dyscyplina3
    )


@pytest.fixture
def grupa_raporty_wyswietlanie():
    from django.contrib.auth.models import Group

    from bpp import const

    return Group.objects.get_or_create(name=const.GR_RAPORTY_WYSWIETLANIE)[0]
