import pytest
from django.contrib.admin import site
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from dynamic_columns.exceptions import CodeAccessNotAllowed
from dynamic_columns.models import ModelAdmin, ModelAdminColumn
from dynamic_columns.util import qual, str_to_class


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


def test_qual_function():
    """Test that qual function returns full import path of a class."""
    from django.contrib.admin import ModelAdmin as DjangoModelAdmin

    result = qual(DjangoModelAdmin)
    assert result == "django.contrib.admin.options.ModelAdmin"


def test_qual_function_custom_class():
    """Test qual function with custom class."""
    result = qual(ModelAdmin)
    assert result == "dynamic_columns.models.ModelAdmin"


def test_str_to_class_valid_path():
    """Test str_to_class with valid module path."""
    result = str_to_class("django.contrib.admin.options.ModelAdmin")

    from django.contrib.admin import ModelAdmin as DjangoModelAdmin

    assert result == DjangoModelAdmin


def test_str_to_class_invalid_path():
    """Test str_to_class raises NameError for invalid class name."""
    with pytest.raises(NameError) as exc_info:
        str_to_class("django.contrib.admin.options.NonExistentClass")

    assert "doesn't exist" in str(exc_info.value)


def test_code_access_not_allowed_exception():
    """Test CodeAccessNotAllowed exception can be raised and caught."""
    with pytest.raises(CodeAccessNotAllowed):
        raise CodeAccessNotAllowed("Test message")


@pytest.mark.django_db
def test_model_admin_str():
    """Test ModelAdmin __str__ returns class_name."""
    ct = ContentType.objects.all().first()
    ma = ModelAdmin.objects.create(class_name="test.admin.TestAdmin", model_ref=ct)
    assert str(ma) == "test.admin.TestAdmin"


@pytest.mark.django_db
def test_model_admin_class_ref_raises_for_unauthorized_path(settings):
    """Test that class_ref raises CodeAccessNotAllowed for unauthorized paths."""
    settings.DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS = ["some.other.module"]

    ct = ContentType.objects.all().first()
    ma = ModelAdmin.objects.create(class_name="unauthorized.path.Admin", model_ref=ct)

    with pytest.raises(CodeAccessNotAllowed) as exc_info:
        _ = ma.class_ref

    assert "unauthorized.path.Admin" in str(exc_info.value)


@pytest.mark.django_db
def test_model_admin_column_unique_constraint():
    """Test that ModelAdminColumn has unique constraint on (parent, col_name)."""
    from django.db import IntegrityError

    ct = ContentType.objects.all().first()
    ma = ModelAdmin.objects.create(class_name="test.UniqueAdmin", model_ref=ct)

    ModelAdminColumn.objects.create(parent=ma, col_name="test_col", ordering=1)

    with pytest.raises(IntegrityError):
        ModelAdminColumn.objects.create(parent=ma, col_name="test_col", ordering=2)
