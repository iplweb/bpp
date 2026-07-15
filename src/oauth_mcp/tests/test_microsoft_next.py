import pytest
from django.apps import apps


@pytest.mark.skipif(
    not apps.is_installed("microsoft_auth"),
    reason="wariant Microsoft nieaktywny w tej konfiguracji",
)
@pytest.mark.django_db
def test_login_zachowuje_next(client):
    resp = client.get("/accounts/login/?next=/o/authorize/%3Ffoo%3Dbar")
    assert resp.status_code == 302
    assert "next=" in resp["Location"]
