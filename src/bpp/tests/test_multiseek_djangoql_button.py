import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_button_visible_for_superuser(client):
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    client.force_login(u)
    resp = client.get(reverse("multiseek:index"))
    assert resp.status_code == 200
    # The button element itself (its id is unique to the gated block; the
    # data-action string also appears in the always-present JS handler, so we
    # assert on the button id which only renders for query-editor users).
    assert b'id="toDjangoqlButton"' in resp.content
    assert b'id="djangoqlDrawer"' in resp.content


@pytest.mark.django_db
def test_button_hidden_for_plain_user(client):
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=False)
    client.force_login(u)
    resp = client.get(reverse("multiseek:index"))
    assert resp.status_code == 200
    assert b'id="toDjangoqlButton"' not in resp.content
    assert b'id="djangoqlDrawer"' not in resp.content
