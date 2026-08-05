import json

import pytest
from django.test import override_settings

# Realny cache (LocMem) zamiast domyślnego DummyCache — inaczej rate-limit jest
# no-opem (cache.add/incr nic nie robią) i nie da się przetestować kubełków.
_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


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


@pytest.mark.django_db
def test_dcr_payload_nie_obiekt_400(client):
    # Poprawny JSON, ale nie obiekt — payload.get() rzuciłby AttributeError.
    resp = client.post(
        "/o/register/",
        data=json.dumps([]),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client_metadata"


@pytest.mark.django_db
def test_dcr_redirect_uri_nie_string_400(client):
    # Element redirect_uris nie-stringiem — re.match rzuciłby TypeError.
    resp = client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": [1234]}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_redirect_uri"


@override_settings(CACHES=_LOCMEM)
@pytest.mark.django_db
def test_dcr_rate_limit_per_realny_klient_nie_per_nginx(client):
    # Uwaga reviewera #7: limiter musi liczyć REALNE IP klienta (proxy-aware),
    # nie REMOTE_ADDR = IP nginxa. W modelu bpp-deploy nginx dokleja realny
    # remote_addr na KOŃCU X-Forwarded-For → prawdziwym IP jest OSTATNI wpis.
    payload = json.dumps({"redirect_uris": ["https://claude.ai/cb"]})

    def zarejestruj(realne_ip):
        # nginx: REMOTE_ADDR = jego własne IP; XFF = "<spoof klienta>, <realne>".
        return client.post(
            "/o/register/",
            data=payload,
            content_type="application/json",
            HTTP_X_FORWARDED_FOR=f"9.9.9.9, {realne_ip}",
            REMOTE_ADDR="10.0.0.1",
        )

    # Klient A wyczerpuje swój limit (20/okno) — 21. próba to 429.
    for _ in range(20):
        assert zarejestruj("1.1.1.1").status_code == 201
    assert zarejestruj("1.1.1.1").status_code == 429

    # Klient B za TYM SAMYM nginxem (ten sam REMOTE_ADDR) ma WŁASNY kubełek.
    # Pod starym kodem (klucz po REMOTE_ADDR) dostałby 429 — globalny DoS.
    assert zarejestruj("2.2.2.2").status_code == 201


@pytest.mark.django_db
def test_dcr_client_name_nie_string_akceptowany(client):
    # client_name nie-string — [:255] rzuciłby TypeError; oczekujemy
    # fallbacku na nazwę domyślną zamiast 500.
    resp = client.post(
        "/o/register/",
        data=json.dumps(
            {"client_name": 123, "redirect_uris": ["https://claude.ai/cb"]}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
