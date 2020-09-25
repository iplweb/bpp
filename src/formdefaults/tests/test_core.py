import pytest
from django import forms

from formdefaults import core
from formdefaults.models import FormRepresentation, FormFieldRepresentation
from formdefaults.util import full_name


class TestForm(forms.Form):
    fld = forms.CharField(label="Takietam", initial=123)


@pytest.fixture
def test_form():
    return TestForm()


@pytest.fixture
def test_form_repr(test_form):
    return FormRepresentation.objects.get_or_create(full_name=full_name(test_form))[0]


@pytest.mark.django_db
def test_update_form_db_repr(test_form, test_form_repr, normal_django_user):
    core.update_form_db_repr(test_form, test_form_repr)
    assert FormFieldRepresentation.objects.count() == 1

    core.update_form_db_repr(test_form, test_form_repr, user=normal_django_user)
    assert FormFieldRepresentation.objects.count() == 2


@pytest.mark.django_db
def test_get_form_defaults(test_form):

    res = core.get_form_defaults(test_form)
    assert res["fld"] == 123


@pytest.mark.django_db
def test_get_form_defaults_with_user(test_form, normal_django_user):

    res = core.get_form_defaults(test_form, user=normal_django_user)
    assert res["fld"] == 123

    o = FormFieldRepresentation.objects.first()
    o.value = 456
    o.save()

    res = core.get_form_defaults(test_form, user=normal_django_user)
    assert res["fld"] == 456

    FormFieldRepresentation.objects.create(
        parent=o.parent, user=normal_django_user, name=o.name, value=786
    )

    res = core.get_form_defaults(test_form, user=normal_django_user)
    assert res["fld"] == 786
