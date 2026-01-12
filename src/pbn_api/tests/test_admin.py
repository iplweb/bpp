import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_api.admin import OswiadczeniaInstytucjiAdmin
from pbn_api.client import PBN_DELETE_PUBLICATION_STATEMENT
from pbn_api.models import OswiadczenieInstytucji
from pbn_api.tests.utils import middleware

from django.contrib.messages import get_messages


def test_SentDataAdmin_list_filter_works(admin_client):
    url = reverse("admin:pbn_api_sentdata_changelist")
    res = admin_client.get(url + "?q=123")
    assert res.status_code == 200


def test_PublisherAdmin_search_works(admin_client):
    url = reverse("admin:pbn_api_publisher_changelist")
    res = admin_client.get(url + "?q=123")
    assert res.status_code == 200


@pytest.mark.django_db
def test_OswiadczenieInstytucji_delete_model(pbn_uczelnia, pbn_client, rf):
    oi = baker.make(OswiadczenieInstytucji)
    req = rf.get("/")

    pbn_client.transport.return_values[
        PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=oi.publicationId_id)
    ] = {"1": "2"}

    with middleware(req):
        OswiadczeniaInstytucjiAdmin(OswiadczenieInstytucji, None).delete_model(
            req, oi, pbn_client=pbn_client
        )

    try:
        OswiadczenieInstytucji.objects.get(pk=oi.pk)
        msg = list(get_messages(req))
        if msg:
            raise Exception(str(msg))
        raise Exception("Nie został skasowany")
    except OswiadczenieInstytucji.DoesNotExist:
        assert True  # good
