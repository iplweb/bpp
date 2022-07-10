from unittest.mock import Mock

import pytest
from model_bakery import baker

from integrator2.models.lista_ministerialna import ListaMinisterialnaElement

from bpp.models.zrodlo import Punktacja_Zrodla, Zrodlo


def test_models_lista_ministerialna_input_file_to_dict_stream(lmi):
    gen = lmi.input_file_to_dict_stream()
    next(gen)
    res = next(gen)
    assert res["nazwa"] == "AAPG BULLETIN"


def test_models_lista_ministerialna_b_alt(lmi_b):
    gen = lmi_b.input_file_to_dict_stream()
    next(gen)
    res = next(gen)
    assert res["nazwa"] == "„Studia Etnologiczne i Antropologiczne”"


def test_models_lista_ministerialna_b(lmi_b):
    gen = lmi_b.input_file_to_dict_stream()
    next(gen)
    res = next(gen)
    assert res["nazwa"] == "„Studia Etnologiczne i Antropologiczne”"


def test_models_lista_ministerialna_c(lmi_c):
    gen = lmi_c.input_file_to_dict_stream()
    next(gen)
    res = next(gen)
    assert res["nazwa"] == "19th Century music"


@pytest.mark.django_db
def test_models_lista_ministerialna_dict_stream_to_db(lmi):
    lmi.dict_stream_to_db(limit=20)
    assert ListaMinisterialnaElement.objects.all().count() == 20


@pytest.mark.django_db
def test_models_lista_ministerialna_match_single_record(lmi):
    z = baker.make(Zrodlo, nazwa="AAPG BULLETIN", issn="1111-1111", e_issn="1234-1234")

    elem = Mock(issn="1111-1111", e_issn=None, nazwa=None)
    lmi.match_single_record(elem)
    assert elem.zrodlo == z

    elem = Mock(issn=None, e_issn="1234-1234", nazwa=None)
    lmi.match_single_record(elem)
    assert elem.zrodlo == z

    elem = Mock(issn=None, e_issn=None, nazwa="AAPG BULLETIN")
    lmi.match_single_record(elem)
    assert elem.zrodlo == z


@pytest.mark.django_db
def test_models_integrate_single_record(lmi):
    z = baker.make(Zrodlo, nazwa="AAPG BULLETIN", issn="1111-1111", e_issn="1234-1234")
    elem = Mock(issn="1111-1111", e_issn=None, nazwa=None, zrodlo=z, punkty_kbn=999)
    elem.parent = Mock(year=2005)

    lmi.integrate_single_record(elem)
    pz = Punktacja_Zrodla.objects.get(zrodlo=z)
    assert pz.punkty_kbn == 999
