from django.urls import reverse


def test_logout(admin_client):
    admin_client.get(reverse("logout"))
