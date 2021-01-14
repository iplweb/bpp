import json

from bpp.views.api import const
from bpp.views.api.pubmed import GetPubmedIDView, get_data_from_ncbi


def test_get_data_from_ncbi(mocker):
    query = mocker.patch("pymed.PubMed.query")
    query.return_value = "123"

    res = get_data_from_ncbi("foobar")
    assert res == ["1", "2", "3"]


def test_GetPubmedIDView_post_nie_ma_tytulu(rf):
    v = GetPubmedIDView()

    req = rf.get("/", data={"t": ""})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_BRAK_PARAMETRU)

    req = rf.get("/", data={"t": "    "})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_BRAK_PARAMETRU)


def test_GetPubmedIDView_post_brak_rezultaut(rf, mocker):

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = []

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_PO_TYTULE_BRAK)


def test_GetPubmedIDView_post_wiele_rezultatow(rf, mocker):

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = ["1", "2", "3"]

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = json.loads(v.post(req).content)
    assert res == dict(error=const.PUBMED_PO_TYTULE_WIELE)


def test_GetPubmedIDView_post_jeden_rezultat(rf, mocker):
    class FakePraca:
        pubmed_id = "lel"
        doi = "lol"
        pmc_id = "pmc_id"
        title = "none"

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = [FakePraca()]

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = json.loads(v.post(req).content)
    assert res["doi"] == "lol"
