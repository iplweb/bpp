import pytest
from django.urls import reverse

from bpp.models import BppUser


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


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_login_microsoft_auth_admin_1(
    admin_user: BppUser, admin_client: "django.test.client.Client"  # noqa
):
    url = reverse("admin:bpp_bppuser_change", args=(admin_user.pk,))
    res = admin_client.get(url)
    # Jeżeli NIE ma microsoft_auth, to nie ma byc "Microsoft accounts" w formularzu
    assert b"Microsoft accounts" not in res.content


@pytest.mark.django_db
def test_login_microsoft_auth_admin_2(
    admin_user: BppUser, admin_client: "django.test.client.Client"  # noqa
):
    url = reverse("admin:bpp_bppuser_change", args=(admin_user.pk,))
    res = admin_client.get(url)
    # Jeżeli JEST microsoft_auth, to NADAL nie ma byc "Microsoft accounts" w formularzu
    assert b"Microsoft accounts" not in res.content
