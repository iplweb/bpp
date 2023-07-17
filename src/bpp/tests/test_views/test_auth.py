import pytest
from django.urls import reverse


def test_logout(admin_client):
    admin_client.get(reverse("logout"))


@pytest.mark.django_db
def test_login(client: "django.test.client.Client"):  # noqa
    url = reverse("login_form") + "?next=/*1*/{{43+53}}"
    res = client.get(url)
    assert res.status_code == 200
