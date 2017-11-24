# -*- encoding: utf-8 -*-
import json

import pytest
from django import forms

from bpp.views.api.uzupelnij_rok import ApiUzupelnijRokWydawnictwoZwarteView, \
    ApiUzupelnijRokWydawnictwoCiagleView


@pytest.mark.django_db
def test_ApiUzupelnijRokWydawnictwoZwarteView_get_data(wydawnictwo_zwarte):
    x = ApiUzupelnijRokWydawnictwoZwarteView()

    test_dict_1 = {'miejsce_i_rok': "Lublin 2000"}
    test_dict_2 = {'wydawnictwo_nadrzedne': wydawnictwo_zwarte}
    res = x.get_data(test_dict_1)
    assert res['rok'] == "2000"

    res = x.get_data(test_dict_2)
    assert res['rok'] == wydawnictwo_zwarte.rok

    test_dict_1.update(test_dict_2)
    res = x.get_data(test_dict_1)

    assert res['rok'] == "2000"


def test_ApiUzupelnijRokWydawnictwoZwarteView_post(rf):
    x = ApiUzupelnijRokWydawnictwoZwarteView()

    class FakeForm(forms.Form):
        sss = forms.CharField(required=True)

    x.validation_form_class = FakeForm

    res = x.post(rf.post("/"))
    assert json.loads(res.content)['error'] == 'form'

    res = x.post(rf.post("/", data={"sss": "123"}))
    assert json.loads(res.content)['rok'] == 'b/d'


def test_ApiUzupelnijRokWydawnictwoCiagleView():
    x = ApiUzupelnijRokWydawnictwoCiagleView()

    test_dict_1 = {'informacje': "Lublin 2000"}
    res = x.get_data(test_dict_1)
    assert res['rok'] == "2000"

    res = x.get_data({'informacje': ''})
    assert res['rok'] == "b/d"

    res = x.get_data({'informacje': 'Lublni 202'})
    assert res['rok'] == "b/d"
