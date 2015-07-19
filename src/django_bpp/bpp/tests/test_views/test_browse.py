# -*- encoding: utf-8 -*-
import json

from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.tests.testutil import UserTestCase
from bpp.views.browse import BuildSearch


class TestViewsBrowse(UserTestCase):
    def test_buildSearch(self):
        dct = {
            'zrodlo': [1, ],
            'typ': [1, ],
            'rok': [2013, ],
            'jednostka': [1, ],
            'autor': [1, ]
        }

        class mydct(dict):
            def getlist(self, value):
                return self.get(value)

        class request:
            POST = mydct(dct)
            META = {}
            session = {}

            def build_absolute_uri(self, *args, **kw):
                return "/absolute/uri"

        tbs = BuildSearch()
        tbs.request = request()
        tbs.post(request)

        self.maxDiff = None

        expected = {u'form_data':
            [None,
              {u'field': u'\u0179r\xf3d\u0142o',
               u'operator': u'r\xf3wne',
               u'prev_op': None,
               u'value': 1},
              {u'field': u'Nazwisko i imi\u0119',
               u'operator': u'r\xf3wne',
               u'prev_op': u'and',
               u'value': 1},
              {u'field': u'Typ rekordu',
               u'operator': u'r\xf3wny',
               u'prev_op': u'and',
               u'value': 1},
              {u'field': u'Jednostka',
               u'operator': u'r\xf3wna',
               u'prev_op': u'and',
               u'value': 1},
              {u'field': u'Rok',
               u'operator': u'r\xf3wny',
               u'prev_op': u'and',
               u'value': 2013}]}

        self.assertEquals(
            json.loads(request.session[MULTISEEK_SESSION_KEY]),
            expected)

