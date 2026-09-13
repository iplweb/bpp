"""PRM (RFC 9728) — wskazuje klientowi, gdzie jest serwer autoryzacji."""

import pytest


@pytest.mark.django_db
def test_prm_zwraca_wlasciwe_urle(client, settings):
    # Django odda 400 (DisallowedHost) dla hosta spoza ALLOWED_HOSTS —
    # bez tego nadpisania test padłby na kliencie testowym, nie na
    # widoku, który mamy zweryfikować.
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    odp = client.get(
        "/.well-known/oauth-protected-resource", HTTP_HOST="bpp.example.test"
    )
    assert odp.status_code == 200
    dane = odp.json()
    assert dane["resource"] == "http://bpp.example.test/mcp"
    assert dane["authorization_servers"] == ["http://bpp.example.test"]
    assert dane["scopes_supported"] == ["read"]


@pytest.mark.django_db
def test_prm_jest_per_host(client, settings):
    """Wielo-domenowość: każda uczelnia widzi swój adres."""
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost", "uczelnia2.localhost"]
    a = client.get(
        "/.well-known/oauth-protected-resource", HTTP_HOST="uczelnia1.localhost"
    ).json()
    b = client.get(
        "/.well-known/oauth-protected-resource", HTTP_HOST="uczelnia2.localhost"
    ).json()
    assert a["resource"] != b["resource"]
