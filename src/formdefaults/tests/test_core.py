import pytest
from django import forms

from formdefaults import core
from formdefaults.models import FormRepresentation
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
    assert test_form_repr.fields_set.count() == 1
    assert test_form_repr.values_set.count() == 1

    core.update_form_db_repr(test_form, test_form_repr, user=normal_django_user)
    assert test_form_repr.fields_set.count() == 1
    assert test_form_repr.values_set.count() == 2


@pytest.mark.django_db
def test_get_form_defaults(test_form):

    res = core.get_form_defaults(test_form)
    assert res["fld"] == 123


@pytest.mark.django_db
def test_get_form_defaults_change_label_form(test_form):
    core.get_form_defaults(test_form, "123")

    core.get_form_defaults(test_form, "456")

    assert FormRepresentation.objects.first().label == "456"


@pytest.mark.django_db
def test_get_form_defaults_change_label_field(test_form, test_form_repr):
    core.get_form_defaults(test_form, "123")
    test_form.fields["fld"].label = "456"

    core.get_form_defaults(test_form, "123")

    assert test_form_repr.fields_set.first().label == "456"


@pytest.mark.django_db
def test_get_form_defaults_undumpable_json(test_form, test_form_repr):
    core.get_form_defaults(test_form, "123")
    assert test_form_repr.fields_set.count() == 1
    assert test_form_repr.values_set.first().value == 123

    test_form.fields["fld"].initial = test_get_form_defaults_undumpable_json
    core.get_form_defaults(test_form, "123")
    assert test_form_repr.values_set.count() == 0


@pytest.mark.django_db
def test_get_form_defaults_with_user(test_form, test_form_repr, normal_django_user):

    res = core.get_form_defaults(test_form, user=normal_django_user)
    assert res["fld"] == 123

    db_field = test_form_repr.fields_set.first()

    o = test_form_repr.values_set.first()
    o.value = 456
    o.save()

    res = core.get_form_defaults(test_form, user=normal_django_user)
    assert res["fld"] == 456

    test_form_repr.values_set.create(
        parent=o.parent, field=db_field, user=normal_django_user, value=786
    )

    res = core.get_form_defaults(test_form, user=normal_django_user)
    assert res["fld"] == 786
