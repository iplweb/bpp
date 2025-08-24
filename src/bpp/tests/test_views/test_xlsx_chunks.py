import pytest
from django.test import Client
from django.urls import reverse

from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import BppUser


@pytest.mark.django_db
def test_xlsx_issn_chunks_unauthorized_access_redirects_to_login():
    """Test that unauthorized users are redirected to login page"""
    client = Client()
    response = client.get(reverse("bpp:xlsx-issn-chunks"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_xlsx_issn_chunks_logged_in_user_without_group_gets_forbidden():
    """Test that logged in users without the required group get 403"""
    user = BppUser.objects.create_user("testuser", "test@example.com", "pass")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("bpp:xlsx-issn-chunks"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_xlsx_issn_chunks_user_with_correct_group_gets_xlsx_file():
    """Test that users with correct group can access the view and get XLSX file"""
    user = BppUser.objects.create_user("testuser", "test@example.com", "pass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)

    client = Client()
    client.force_login(user)
    response = client.get(reverse("bpp:xlsx-issn-chunks"))

    assert response.status_code == 200
    assert (
        response["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "issn_czasopism_" in response["Content-Disposition"]
    assert "attachment" in response["Content-Disposition"]
