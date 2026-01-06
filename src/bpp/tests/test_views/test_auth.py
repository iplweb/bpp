import pytest
from django.urls import reverse

from bpp.models import BppUser


def test_logout(admin_client):
    admin_client.get(reverse("logout"))


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_logout_unauthenticated_user(client):
    """Test that unauthenticated user accessing /logout/ is redirected to login page"""
    response = client.get(reverse("logout"))
    # Should redirect to login page (302) with next parameter
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
def test_logout_unauthenticated_user_microsoft(client):
    """
    Test that unauthenticated user accessing /logout/ with MicrosoftLogoutView
    is redirected directly to post_logout_redirect_uri without errors
    """
    response = client.get(reverse("logout"))
    # MicrosoftLogoutView should redirect unauthenticated users directly
    # to post_logout_redirect_uri instead of going through Microsoft logout
    assert response.status_code == 302
    # Should not cause AttributeError from easyaudit


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_login_1(client: "django.test.client.Client"):  # noqa
    url = reverse("login_form") + "?next=/*1*/{{43+53}}"
    res = client.get(url)
    assert res.status_code == 200


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_login_2(client: "django.test.client.Client"):  # noqa
    url = reverse("login_form") + "?next={{987+654}}"
    res = client.get(url)
    assert b"1641" not in res.content


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
