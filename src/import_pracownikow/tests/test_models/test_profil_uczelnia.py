"""``ProfilMapowania`` per-uczelnia: manager ``dla_uczelni`` + unique_together."""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ProfilMapowania


@pytest.mark.django_db
def test_dla_uczelni_multi_tenant_scisle():
    """>1 uczelnia: ``dla_uczelni(A)`` zwraca tylko profile A (nie B, nie NULL)."""
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    p_a = baker.make(ProfilMapowania, nazwa="A", uczelnia=a)
    baker.make(ProfilMapowania, nazwa="B", uczelnia=b)
    baker.make(ProfilMapowania, nazwa="Legacy", uczelnia=None)
    wynik = set(ProfilMapowania.objects.dla_uczelni(a))
    assert wynik == {p_a}


@pytest.mark.django_db
def test_dla_uczelni_single_tenant_zawiera_null():
    """Jedna uczelnia: ``dla_uczelni(A)`` zwraca profile A ORAZ legacy NULL."""
    a = baker.make(Uczelnia)
    Uczelnia.objects.exclude(pk=a.pk).delete()
    p_a = baker.make(ProfilMapowania, nazwa="A", uczelnia=a)
    p_legacy = baker.make(ProfilMapowania, nazwa="Legacy", uczelnia=None)
    wynik = set(ProfilMapowania.objects.dla_uczelni(a))
    assert wynik == {p_a, p_legacy}


@pytest.mark.django_db
def test_ta_sama_nazwa_na_dwoch_uczelniach():
    """``unique_together (uczelnia, nazwa)`` dopuszcza tę samą nazwę na 2 uczelniach."""
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    baker.make(ProfilMapowania, nazwa="Kwartalny", uczelnia=a)
    baker.make(ProfilMapowania, nazwa="Kwartalny", uczelnia=b)  # nie rzuca
    assert ProfilMapowania.objects.filter(nazwa="Kwartalny").count() == 2
