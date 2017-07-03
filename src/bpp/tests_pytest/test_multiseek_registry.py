# -*- encoding: utf-8 -*-
import pytest
from multiseek.logic import CONTAINS, NOT_CONTAINS, STARTS_WITH, \
    NOT_STARTS_WITH

from bpp.models.cache import Rekord
from bpp.multiseek_registry import TytulPracyQueryObject


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["foo", "bar", u"łódź"])
@pytest.mark.parametrize("operation",
                         [CONTAINS, NOT_CONTAINS,
                          STARTS_WITH, NOT_STARTS_WITH])
def test_TytulPracyQueryObject(value, operation):
    ret = TytulPracyQueryObject(
        field_name='tytul_oryginalny',
        label="Tytuł oryginalny",
        public=True
    ).real_query(value, operation)
    assert Rekord.objects.filter(*(ret,)).count() == 0