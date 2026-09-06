"""Strona /mcp/ — instrukcja podłączenia dla człowieka."""

import pytest


@pytest.mark.django_db
def test_strona_pokazuje_oba_adresy(client, settings):
    # Bez nadpisania ALLOWED_HOSTS Django odda 400 dla obcego Hosta,
    # zanim widok zdąży zbudować adresy (patrz test_cache_vary_host.py).
    settings.ALLOWED_HOSTS = ["bpp.example.test"]

    odp = client.get("/mcp/", HTTP_HOST="bpp.example.test")

    assert odp.status_code == 200
    tresc = odp.content.decode()
    assert "http://bpp.example.test/mcp" in tresc
    assert "http://bpp.example.test/mcp/auth" in tresc


@pytest.mark.django_db
def test_adresy_sa_per_host(client, settings):
    settings.ALLOWED_HOSTS = ["uczelnia1.localhost"]

    a = client.get("/mcp/", HTTP_HOST="uczelnia1.localhost").content.decode()

    assert "uczelnia1.localhost/mcp" in a
