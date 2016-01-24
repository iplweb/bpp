# -*- encoding: utf-8 -*-
import json
import re

from django.core.urlresolvers import reverse
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.tests.testutil import UserTestCase
from bpp.views.browse import BuildSearch
from bs4 import BeautifulSoup


def test_buildSearch():
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

    assert json.loads(request.session[MULTISEEK_SESSION_KEY]) == expected

pattern = re.compile("Strona WWW")

def nastepna_komorka_po_strona_www(dokument):
    soup = BeautifulSoup(dokument, 'html.parser')
    return soup.find("th", text=pattern).parent.find("td").text.strip()

def test_darmowy_platny_dostep_www_wyswietlanie(client, wydawnictwo_ciagle):
    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=('wydawnictwo_ciagle', wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'Brak danych'

    wydawnictwo_ciagle.www = "platny"
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=('wydawnictwo_ciagle', wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'platny'

    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=('wydawnictwo_ciagle', wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'darmowy'

    wydawnictwo_ciagle.www = "jezeli sa oba ma byc darmowy"
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=('wydawnictwo_ciagle', wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'darmowy'
