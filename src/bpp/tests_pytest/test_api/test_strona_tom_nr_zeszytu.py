# -*- encoding: utf-8 -*-


import json

from bpp.views.api.strona_tom_nr_zeszytu import StronaTomNrZeszytuView


def test_api_strona_tom_nr_zeszytu():
    class FakeReq2:
        POST = {'s': 's. 22-33',
                'i': '1992 vol. 5 z. 4'}

    x = StronaTomNrZeszytuView().post(FakeReq2())
    ret = json.loads(x.content)

    assert ret['strony'] == '22-33'
    assert ret['tom'] == '5'
    assert ret['nr_zeszytu'] == '4'
