import pytest
from django.urls import reverse
from model_mommy import mommy

from pbn_api.admin import OswiadczeniaInstytucjiAdmin
from pbn_api.client import PBN_DELETE_PUBLICATION_STATEMENT
from pbn_api.models import OswiadczenieInstytucji
from pbn_api.tests.utils import middleware


def test_SentDataAdmin_list_filter_works(admin_client):
    url = reverse("admin:pbn_api_sentdata_changelist")
    res = admin_client.get(url + "?q=123")
    assert res.status_code == 200


@pytest.mark.django_db
def test_OswiadczenieInstytucji_delete_model(pbn_uczelnia, pbnclient, rf):
    oi = mommy.make(OswiadczenieInstytucji)
    req = rf.get("/")

    pbnclient.transport.return_values[
        PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=oi.publicationId_id)
    ] = {"1": "2"}

    with middleware(req):
        OswiadczeniaInstytucjiAdmin(OswiadczenieInstytucji, None).delete_model(
            req, oi, pbn_client=pbnclient
        )

    with pytest.raises(OswiadczenieInstytucji.DoesNotExist):
        oi.refresh_from_db()
