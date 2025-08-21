import pytest
from django.urls import reverse


def test_logout(admin_client):
    admin_client.get(reverse("logout"))


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_login_1(client: "django.test.client.Client"):  # noqa
    url = reverse("login_form") + "?next=/*1*/{{43+53}}"
    res = client.get(url)
    assert res.status_code == 200


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_login_2(client: "django.test.client.Client"):  # noqa
    url = reverse("login_form") + "?next={{101+205}}"
    res = client.get(url)
    assert b"306" not in res.content
