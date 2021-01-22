# -*- encoding: utf-8 -*-
import xml.etree.ElementTree as ET

import pytest
from django.urls.base import reverse


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


def toXML(response):
    return ET.fromstring(response.content.decode("utf-8"))


def test_listRecords(ksiazka, client):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = client.get(listRecords)

    ET.fromstring(res.content.decode("utf-8"))
    assert "Tytul Wydawnictwo" in toXML(res)[2][0][1][0][1].text


def test_listRecords_status_korekty(
    ksiazka, client, uczelnia, przed_korekta, po_korekcie
):
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    ksiazka.status_korekty = przed_korekta
    ksiazka.save()

    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = toXML(client.get(listRecords))

    with pytest.raises(IndexError):
        assert "Tytul Wydawnictwo" in res[2][0][1][0][1].text

    ksiazka.status_korekty = po_korekcie
    ksiazka.save()
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    res = toXML(client.get(listRecords))

    assert "Tytul Wydawnictwo" in res[2][0][1][0][1].text


def test_listRecords_no_queries_zwarte(ksiazka, client, django_assert_max_num_queries):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    with django_assert_max_num_queries(5):
        res = client.get(listRecords)
    assert "Tytul Wydawnictwo" in toXML(res)[2][0][1][0][1].text


def test_listRecords_no_queries_ciagle(artykul, client, django_assert_max_num_queries):
    listRecords = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    with django_assert_max_num_queries(5):
        res = client.get(listRecords)
    assert "Tytul Wydawnictwo" in toXML(res)[2][0][1][0][1].text
