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
    res = v.post(req)
    assert res.content == b"{}"

    req = rf.get("/", data={"t": "    "})
    v.post(req)
    assert res.content == b"{}"


def test_GetPubmedIDView_post_brak_rezultaut(rf, mocker):

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = []

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = v.post(req)
    assert res.content == const.PUBMED_PO_TYTULE_BRAK


def test_GetPubmedIDView_post_wiele_rezultatow(rf, mocker):

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = ["1", "2", "3"]

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = v.post(req)
    assert res.content == const.PUBMED_PO_TYTULE_WIELE


def test_GetPubmedIDView_post_jeden_rezultat(rf, mocker):
    dct = {"hey": "hey"}

    class FakePraca:
        def toJSON(self):
            return dct

    query = mocker.patch("pymed.PubMed.query")
    query.return_value = [FakePraca()]

    v = GetPubmedIDView()

    req = rf.post("/", data={"t": "razd dwa trzy test"})
    res = v.post(req)
    assert res.content.decode("ascii") == str(dct).replace("'", '"')
