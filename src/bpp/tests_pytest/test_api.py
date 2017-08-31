import json
from bpp.views.api import pubmed
import os
import pytest

from bpp.views.api.strona_tom_nr_zeszytu import StronaTomNrZeszytuView


@pytest.mark.parametrize("filename,count", [
    ('api_pubmed_xml_single.html', 1),
    ('api_pubmed_xml_none.html', 0),
    ('api_pubmed_xml_multiple.html', 20),
])
def test_get_pubmed_xml_single(filename, count, httpserver):
    httpserver.serve_content(open(
        os.path.join(os.path.dirname(__file__), filename), "rb").read())

    data = pubmed.get_data_from_ncbi(title='whateva', url=httpserver.url)
    assert len(data) == count


def test_parse_pubmed_xml(httpserver):
    httpserver.serve_content(open(
        os.path.join(os.path.dirname(__file__), 'api_pubmed_xml_single.html')).read())

    data = pubmed.get_data_from_ncbi(title='whateva', url=httpserver.url)
    assert len(data) == 1

    ret = pubmed.parse_data_from_ncbi(data[0])
    assert ret['has_abstract_text'] == 'true'

    assert ret['doi']


def test_GetPubmedIDView(monkeypatch):
    def get_data_from_ncbi(title):
        return ['123']

    def parse_data_from_ncbi(data):
        return {'foo': 'bar'}

    monkeypatch.setattr(pubmed, 'get_data_from_ncbi', get_data_from_ncbi)
    monkeypatch.setattr(pubmed, 'parse_data_from_ncbi', parse_data_from_ncbi)

    class FakeReq:
        POST = {'t': 'foo'}

    x = pubmed.GetPubmedIDView().post(FakeReq())
    assert json.loads(x.content)['foo'] == 'bar'


def test_GetPubmedIDView_second(monkeypatch):
    def get_data_from_ncbi_2(title):
        return []

    class FakeReq:
        POST = {'t': 'foo'}

    monkeypatch.setattr(pubmed, 'get_data_from_ncbi', get_data_from_ncbi_2)
    x = pubmed.GetPubmedIDView().post(FakeReq())
    assert json.loads(x.content) == {}


def test_GetPubmedView_EmptyReq():
    class FakeReq2:
        POST = {}

    x = pubmed.GetPubmedIDView().post(FakeReq2())
    assert json.loads(x.content) == {}


def test_api_strona_tom_nr_zeszytu():

    class FakeReq2:
        POST = {'s': 's. 22-33',
                'i': '1992 vol. 5 z. 4'}

    x = StronaTomNrZeszytuView().post(FakeReq2())
    ret = json.loads(x.content)

    assert ret['strony'] == '22-33'
    assert ret['tom'] == '5'
    assert ret['nr_zeszytu'] == '4'