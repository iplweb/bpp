"""Testy konfiguracji adminów dot. profilu autora."""

import pytest
from django.contrib.admin.sites import site

from bpp.models import Autor, Uczelnia

pytestmark = pytest.mark.django_db


def _pola_fieldsetow(admin_obj):
    pola = []
    for _nazwa, opcje in admin_obj.fieldsets:
        pola.extend(opcje["fields"])
    return pola


def test_edytor_ukladu_jest_na_uczelni():
    admin_obj = site._registry[Uczelnia]
    assert "uklad_profilu_autora" in _pola_fieldsetow(admin_obj)


def test_uklad_zniknal_z_admina_autora():
    admin_obj = site._registry[Autor]
    assert "uklad_profilu" not in _pola_fieldsetow(admin_obj)
