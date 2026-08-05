from django.contrib import admin as djadmin
from django.contrib.admin.utils import flatten_fieldsets

from bpp.admin.autor import Autor_JednostkaInlineForm, AutorAdmin, AutorForm
from bpp.models import StanowiskoDydaktyczne, StopienSluzbowy


def test_slowniki_zarejestrowane_w_adminie():
    assert StopienSluzbowy in djadmin.site._registry
    assert StanowiskoDydaktyczne in djadmin.site._registry


def test_autorform_ma_pole_stopien_sluzbowy():
    assert "stopien_sluzbowy" in AutorForm.base_fields
    assert "stopien_sluzbowy" in flatten_fieldsets(AutorAdmin.fieldsets)


def test_inline_autor_jednostka_ma_pole_stanowisko():
    assert "stanowisko" in Autor_JednostkaInlineForm.base_fields
