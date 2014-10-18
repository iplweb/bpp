# -*- encoding: utf-8 -*-
import json
from django.core.urlresolvers import reverse
from multiseek.views import MULTISEEK_SESSION_KEY
from bpp.models.system import Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.util import any_ciagle, any_autor, any_jednostka

from bpp.tests.testutil import UserTestCase, WebTestCase
from bpp.views.browse import BuildSearch
from django.test import TestCase

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
            session = {}

        tbs = BuildSearch()
        tbs.request = request
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
              {u'field': u'Jednostka dowolnego autora',
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

