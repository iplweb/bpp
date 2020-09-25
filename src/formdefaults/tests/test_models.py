from datetime import datetime

import pytest
from django import forms

from formdefaults.models import FormRepresentantion


class TestForm(forms.Form):
    test = forms.DateTimeField(label="test1", initial=datetime.now())


@pytest.mark.django_db
def test_FormRepresentationManager_get_for_instance():
    res = FormRepresentantion.object.get_or_create_for_instance(TestForm())
    assert res.full_name == "formdefaults.tests.test_models.TestForm"
