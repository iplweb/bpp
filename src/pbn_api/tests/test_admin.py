import pytest
from django.urls import reverse
from model_bakery import baker
from selenium.webdriver.support.wait import WebDriverWait

from pbn_api.admin import OswiadczeniaInstytucjiAdmin
from pbn_api.client import PBN_DELETE_PUBLICATION_STATEMENT
from pbn_api.models import OswiadczenieInstytucji, SentData
from pbn_api.tests.utils import middleware

from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages

from django_bpp.selenium_util import LONG_WAIT_TIME, wait_for_page_load


def test_SentDataAdmin_list_filter_works(admin_client):
    url = reverse("admin:pbn_api_sentdata_changelist")
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


@pytest.mark.django_db
def test_pbn_api_admin_SentDataAdmin_wyslij_ponownie(
    wydawnictwo_zwarte, admin_browser, asgi_live_server
):

    s = SentData.objects.create(
        object_id=wydawnictwo_zwarte.pk,
        content_type=ContentType.objects.get_for_model(wydawnictwo_zwarte),
        data_sent={"foo": "bar"},
    )

    with wait_for_page_load(admin_browser):
        admin_browser.visit(
            asgi_live_server.url + f"/admin/pbn_api/sentdata/{s.pk}/change"
        )

    elem = admin_browser.find_by_id("wyslij-ponownie")

    with wait_for_page_load(admin_browser):
        elem.click()

    WebDriverWait(admin_browser, LONG_WAIT_TIME).until(
        lambda *args, **kw: "nie będzie eksportowany" in admin_browser.html
    )
    assert True
