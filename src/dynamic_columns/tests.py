import pytest
from django.urls import reverse

from dynamic_columns.models import ModelAdmin, ModelAdminColumn

from django.contrib.admin import site
from django.contrib.contenttypes.models import ContentType


def test_autor_admin_hide_column(admin_app, autor_jan_kowalski):
    POPRZEDNIE_NAZWISKA = "159ygquadfja0eth0qjaoidjgo"

    autor_jan_kowalski.poprzednie_nazwiska = POPRZEDNIE_NAZWISKA
    autor_jan_kowalski.save()

    # Open the admin, so DynamicColumnMixin.enabled will be called
    res = admin_app.get(reverse("admin:bpp_autor_changelist"))
    assert "Kowalski" in res

    # Get the instance of AutorAdmin
    autor_admin = site._registry.get(autor_jan_kowalski.__class__)

    ma = ModelAdmin.objects.enable(autor_admin)
    c = ma.modeladmincolumn_set.get(col_name="poprzednie_nazwiska")
    c.enabled = True
    c.save()

    # Open the 'default' admin instance
    res = admin_app.get(reverse("admin:bpp_autor_changelist"))
    assert POPRZEDNIE_NAZWISKA in res
    assert "Kowalski" in res

    ma = ModelAdmin.objects.db_repr(autor_admin)
    c = ma.modeladmincolumn_set.get(col_name="poprzednie_nazwiska")
    c.enabled = False
    c.save()

    res = admin_app.get(reverse("admin:bpp_autor_changelist"))
    assert POPRZEDNIE_NAZWISKA not in res
    assert "Kowalski" in res


@pytest.mark.django_db
def test_ModelAdminColumn___str__():

    b = ModelAdminColumn(col_name="bar")
    assert str(b) == 'Column "bar"'

    a = ModelAdmin.objects.create(
        class_name="foo", model_ref=ContentType.objects.all().first()
    )
    b.parent = a

    assert str(b) == 'Column "bar" of model "foo"'
