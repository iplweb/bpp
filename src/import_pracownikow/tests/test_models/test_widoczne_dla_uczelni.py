"""``ImportPracownikow.widoczne_dla_uczelni`` — scoping listy do uczelni."""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_multi_tenant_scisle():
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    imp_a = baker.make(ImportPracownikow, uczelnia=a)
    baker.make(ImportPracownikow, uczelnia=b)
    baker.make(ImportPracownikow, uczelnia=None)  # legacy — ukryty na multi
    assert set(ImportPracownikow.widoczne_dla_uczelni(a)) == {imp_a}


@pytest.mark.django_db
def test_single_tenant_zawiera_null():
    a = baker.make(Uczelnia)
    Uczelnia.objects.exclude(pk=a.pk).delete()
    imp_a = baker.make(ImportPracownikow, uczelnia=a)
    imp_legacy = baker.make(ImportPracownikow, uczelnia=None)
    assert set(ImportPracownikow.widoczne_dla_uczelni(a)) == {imp_a, imp_legacy}
