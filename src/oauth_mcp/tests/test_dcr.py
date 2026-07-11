import json

import pytest


@pytest.mark.django_db
def test_dcr_dozwolony_redirect_201(client):
    resp = client.post(
        "/o/register/",
        data=json.dumps(
            {"client_name": "Claude", "redirect_uris": ["https://claude.ai/cb"]}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["client_id"]
    assert resp.json()["token_endpoint_auth_method"] == "none"


@pytest.mark.django_db
def test_dcr_niedozwolony_redirect_400(client):
    resp = client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["https://evil.example/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_dcr_nie_https_400(client):
    resp = client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["http://evil.example/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_dcr_bez_csrf_dziala():
    # Domyślny test client ma enforce_csrf_checks=False → nie dowiódłby niczego.
    # Wymuszamy CSRF, by realnie przetestować csrf_exempt (W3).
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    resp = csrf_client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["http://localhost:8765/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 201
