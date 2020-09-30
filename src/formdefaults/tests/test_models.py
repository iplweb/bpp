import pytest
from django import forms
from django.core.exceptions import ValidationError

from formdefaults.core import update_form_db_repr
from formdefaults.models import FormRepresentation, FormFieldRepresentation


class TestForm(forms.Form):
    test = forms.IntegerField(label="test1", initial=50)


class AnotherTestForm(forms.Form):
    field = forms.CharField()


@pytest.mark.django_db
def test_FormRepresentationManager_get_for_instance():
    res = FormRepresentation.objects.get_or_create_for_instance(TestForm())
    assert res.full_name == "formdefaults.tests.test_models.TestForm"


def test_FormRepresentation_str():
    a = FormRepresentation()
    assert str(a) is not None


def test_FormFieldRepresentation_str():
    a = FormFieldRepresentation()
    assert str(a) is not None


@pytest.fixture
def test_form():
    return TestForm()


@pytest.fixture
def another_test_form_representation():
    return FormRepresentation.objects.get_or_create_for_instance(AnotherTestForm())


@pytest.fixture
def test_form_repr(test_form):
    return FormRepresentation.objects.get_or_create_for_instance(test_form)


@pytest.fixture
def test_field_value_repr(test_form, test_form_repr):
    update_form_db_repr(test_form, test_form_repr)
    return test_form_repr.values_set.first()


@pytest.mark.django_db
def test_FormRepresentation_get_form_class(test_form_repr):
    assert test_form_repr.get_form_class() == TestForm


@pytest.mark.django_db
def test_FormFieldDefaultValue_clean_parent_different(
    test_form_repr, test_field_value_repr, another_test_form_representation
):
    assert test_field_value_repr.parent == test_form_repr

    test_field_value_repr.parent = None
    with pytest.raises(ValidationError, match=r".* być określony .*"):
        test_field_value_repr.clean()

    test_field_value_repr.parent = another_test_form_representation
    with pytest.raises(ValidationError, match=r".*identyczny.*"):
        test_field_value_repr.clean()


@pytest.mark.django_db
def test_FormFieldDefaultValue_clean_form_class_not_found(
    test_form_repr, test_field_value_repr
):
    test_form_repr.full_name = "123 test"
    test_form_repr.save()

    with pytest.raises(ValidationError, match=r".* klasy formularza .*"):
        test_field_value_repr.clean()


@pytest.mark.django_db
def test_FormFieldDefaultValue_default_value_wrong(
    test_form_repr, test_field_value_repr
):
    test_field_value_repr.value = "this is not a datetime"
    with pytest.raises(ValidationError, match=r"Nie udało .*"):
        test_field_value_repr.clean()
