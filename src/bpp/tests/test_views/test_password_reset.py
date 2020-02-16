from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_password_reset(client):
    client.get(reverse("password_reset"))
