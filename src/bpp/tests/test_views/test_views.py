from bpp.views import update_multiseek_title


def test_update_multiseek_title(rf):
    req = rf.post("/", data={"value": "test\r\nof\nfun"})
    req.session = {}
    res = update_multiseek_title(req)
    assert res.content == b'"test<br>of<br>fun"'
