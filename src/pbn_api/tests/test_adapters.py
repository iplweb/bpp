from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter


def test_WydawnictwoPBNAdapter_ciagle(pbn_wydawnictwo_ciagle):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_ciagle).pbn_get_json()
    assert res["journal"]


def test_WydawnictwoPBNAdapter_zwarte_ksiazka(pbn_wydawnictwo_zwarte_ksiazka):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_ksiazka).pbn_get_json()
    assert not res.get("journal")


def test_WydawnictwoPBNAdapter_zwarte_rozdzial(pbn_wydawnictwo_zwarte_rozdzial):
    res = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_rozdzial).pbn_get_json()
    assert not res.get("journal")
