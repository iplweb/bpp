# -*- encoding: utf-8 -*-
import json
import re

import pytest
from bs4 import BeautifulSoup
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse

from bpp.views.browse import BuildSearch
from multiseek.logic import EQUAL_NONE, EQUAL, EQUAL_FEMALE
from multiseek.views import MULTISEEK_SESSION_KEY


def test_buildSearch(settings):
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

    settings.LANGUAGE_CODE = "en"
    tbs = BuildSearch()
    tbs.request = request()
    tbs.post(request)

    expected = {'form_data':
        [None,
          {'field': '\u0179r\xf3d\u0142o',
           'operator': str(EQUAL_NONE),
           'prev_op': None,
           'value': 1},
          {'field': 'Nazwisko i imi\u0119',
           'operator': str(EQUAL_NONE),
           'prev_op': 'and',
           'value': 1},
          {'field': 'Typ rekordu',
           'operator': str(EQUAL),
           'prev_op': 'and',
           'value': 1},
          {'field': 'Jednostka',
           'operator': str(EQUAL_FEMALE),
           'prev_op': 'and',
           'value': 1},
          {'field': 'Rok',
           'operator': str(EQUAL),
           'prev_op': 'and',
           'value': 2013}]}

    assert json.loads(request.session[MULTISEEK_SESSION_KEY]) == expected

pattern = re.compile("Strona WWW")

def nastepna_komorka_po_strona_www(dokument):
    soup = BeautifulSoup(dokument, 'html.parser')
    return soup.find("th", text=pattern).parent.find("td").text.strip()

@pytest.mark.django_db
def test_darmowy_platny_dostep_www_wyswietlanie(client, wydawnictwo_ciagle):
    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=(
    ContentType.objects.get(app_label='bpp', model='wydawnictwo_ciagle').pk,
    wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'Brak danych'

    wydawnictwo_ciagle.www = "platny"
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=(
    ContentType.objects.get(app_label='bpp', model='wydawnictwo_ciagle').pk,
    wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'platny'

    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=(
    ContentType.objects.get(app_label='bpp', model='wydawnictwo_ciagle').pk,
    wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'darmowy'

    wydawnictwo_ciagle.www = "jezeli sa oba ma byc darmowy"
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(reverse("bpp:browse_praca", args=(
    ContentType.objects.get(app_label='bpp', model='wydawnictwo_ciagle').pk,
    wydawnictwo_ciagle.pk,)))
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == 'darmowy'
