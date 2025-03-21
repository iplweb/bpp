import pytest
from model_bakery import baker

from pbn_api.exceptions import TlumaczDyscyplinException
from pbn_api.models import TlumaczDyscyplin

from bpp.models import Dyscyplina_Naukowa


def test_tlumacz_dyscyplin_bez_aktualnej(pbn_dyscyplina1):
    dyscyplina1 = baker.make(Dyscyplina_Naukowa)
    TlumaczDyscyplin.objects.create(
        dyscyplina_w_bpp=dyscyplina1,
        pbn_2024_now=pbn_dyscyplina1,
        pbn_2022_2023=None,
        pbn_2017_2021=pbn_dyscyplina1,
    )

    with pytest.raises(TlumaczDyscyplinException):
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2022)


def test_tlumacz_dyscyplin_bez_nieaktualnej(pbn_dyscyplina1):
    dyscyplina1 = baker.make(Dyscyplina_Naukowa)

    TlumaczDyscyplin.objects.create(
        dyscyplina_w_bpp=dyscyplina1,
        pbn_2022_2023=pbn_dyscyplina1,
        pbn_2024_now=pbn_dyscyplina1,
        pbn_2017_2021=None,
    )

    with pytest.raises(TlumaczDyscyplinException):
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2017)


@pytest.mark.django_db
def test_tlumacz_dyscyplin_bez_wpisu_w_ogole():
    dyscyplina1 = baker.make(Dyscyplina_Naukowa)

    with pytest.raises(TlumaczDyscyplinException):
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 3050)


def test_tlumacz_dyscyplin_obydwie(pbn_dyscyplina1):
    dyscyplina1 = baker.make(Dyscyplina_Naukowa)

    TlumaczDyscyplin.objects.create(
        dyscyplina_w_bpp=dyscyplina1,
        pbn_2022_2023=pbn_dyscyplina1,
        pbn_2024_now=pbn_dyscyplina1,
        pbn_2017_2021=pbn_dyscyplina1,
    )

    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2017)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2018)
        == pbn_dyscyplina1
    )

    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2019)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2020)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2021)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2022)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2023)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2024)
        == pbn_dyscyplina1
    )
    assert (
        TlumaczDyscyplin.objects.przetlumacz_dyscypline(dyscyplina1, 2025)
        == pbn_dyscyplina1
    )
