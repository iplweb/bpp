# -*- encoding: utf-8 -*-
import pytest
from django.urls.base import reverse
import xml.etree.ElementTree as ET

from bpp.models import Rekord


@pytest.mark.django_db
def test_proper_content_type(client):
    url = reverse("bpp:oai")
    url += "/oai-pmh-repository.xml?verb=Identify"
    res = client.get(url)
    assert "xml" in res["Content-type"]


def test_identify(wydawnictwo_ciagle, client):
    identify = reverse("bpp:oai") + "?verb=Identify"
    res = client.get(identify)
    assert res.status_code == 200


@pytest.fixture
def ksiazka(wydawnictwo_zwarte, ksiazka_polska):
    wydawnictwo_zwarte.charakter_formalny = ksiazka_polska
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


@pytest.fixture
def artykul(
    wydawnictwo_ciagle,
):
    wydawnictwo_zwarte.charakter_formalny = ksiazka_polska
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


def test_listRecords(ksiazka, client):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = client.get(listRecords)

    responseXml = ET.fromstring(res.content.decode("utf-8"))
    assert "Tytul Wydawnictwo" in responseXml[2][0][1][0][1].text


def test_listRecords_status(ksiazka, client):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = client.get(listRecords)

    responseXml = ET.fromstring(res.content.decode("utf-8"))
    assert "Tytul Wydawnictwo" in responseXml[2][0][1][0][1].text
    raise NotImplementedError


def test_listRecords_no_queries_zwarte(ksiazka, client):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = client.get(listRecords)
    raise NotImplementedError


def test_listRecords_no_queries_zwarte(artykul, client):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = client.get(listRecords)
    raise NotImplementedError
