"""Testy integracji konferencji PBN → BPP."""

import datetime

import pytest
from model_bakery import baker

from bpp.models import Konferencja
from pbn_api.models import Conference
from pbn_integrator.utils import integruj_konferencje


def _make_conference(mongo_id, obj):
    """Utwórz lustro Conference z podanym JSON-em 'object'."""
    return baker.make(
        Conference,
        mongoId=mongo_id,
        versions=[{"current": True, "object": obj}],
        status="ACTIVE",
    )


@pytest.mark.django_db
def test_tworzy_konferencje_z_lustra():
    _make_conference(
        "c1",
        {
            "fullName": "Międzynarodowa Konferencja XYZ",
            "startDate": "2023-09-01",
            "endDate": "2023-09-03",
            "city": "Kraków",
            "country": "Polska",
            "abbreviation": "MKXYZ",
        },
    )

    liczba = integruj_konferencje()

    assert liczba == 1
    k = Konferencja.objects.get()
    assert k.nazwa == "Międzynarodowa Konferencja XYZ"
    assert k.rozpoczecie == datetime.date(2023, 9, 1)
    assert k.zakonczenie == datetime.date(2023, 9, 3)
    assert k.miasto == "Kraków"
    assert k.panstwo == "Polska"
    assert k.skrocona_nazwa == "MKXYZ"
    assert k.pbn_uid_id == "c1"


@pytest.mark.django_db
def test_idempotentne_po_pbn_uid():
    _make_conference("c1", {"fullName": "Konf A", "startDate": "2022-01-01"})
    integruj_konferencje()
    integruj_konferencje()
    assert Konferencja.objects.filter(pbn_uid_id="c1").count() == 1


@pytest.mark.django_db
def test_dowiazuje_istniejaca_po_nazwie_i_dacie():
    Konferencja.objects.create(nazwa="Konf B", rozpoczecie=datetime.date(2021, 5, 5))
    _make_conference(
        "c2", {"fullName": "Konf B", "startDate": "2021-05-05", "city": "Łódź"}
    )

    integruj_konferencje()

    assert Konferencja.objects.count() == 1
    k = Konferencja.objects.get()
    assert k.pbn_uid_id == "c2"
    assert k.miasto == "Łódź"


@pytest.mark.django_db
def test_pomija_status_deleted():
    baker.make(
        Conference,
        mongoId="c3",
        versions=[{"current": True, "object": {"fullName": "Konf C"}}],
        status="DELETED",
    )
    assert integruj_konferencje() == 0
    assert Konferencja.objects.count() == 0


@pytest.mark.django_db
def test_zla_data_daje_none_bez_bledu():
    _make_conference("c4", {"fullName": "Konf D", "startDate": "niepoprawna-data"})
    assert integruj_konferencje() == 1
    k = Konferencja.objects.get(pbn_uid_id="c4")
    assert k.rozpoczecie is None


@pytest.mark.django_db
def test_pomija_rekord_bez_nazwy():
    _make_conference("c5", {"startDate": "2020-01-01"})
    assert integruj_konferencje() == 0
    assert Konferencja.objects.count() == 0


@pytest.mark.django_db
def test_przycina_zbyt_dlugie_pola():
    _make_conference(
        "c6",
        {
            "fullName": "x" * 600,
            "abbreviation": "y" * 300,
            "city": "z" * 150,
            "country": "w" * 150,
            "startDate": "2020-01-01",
        },
    )
    assert integruj_konferencje() == 1
    k = Konferencja.objects.get(pbn_uid_id="c6")
    assert len(k.nazwa) == 512
    assert len(k.skrocona_nazwa) == 250
    assert len(k.miasto) == 100
    assert len(k.panstwo) == 100
