# -*- encoding: utf-8 -*-
import pytest
from django.urls.base import reverse


@pytest.mark.django_db
def test_proper_content_type(client):
    url = reverse("bpp:oai")
    url += "/oai-pmh-repository.xml?verb=Identify"
    res = client.get(url)
    assert "xml" in res['Content-type']
