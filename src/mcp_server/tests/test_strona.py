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


def _strona(client, settings, host="bpp.example.test"):
    settings.ALLOWED_HOSTS = [host]
    odp = client.get("/mcp/", HTTP_HOST=host)
    assert odp.status_code == 200
    return odp


@pytest.mark.django_db
def test_prompt_dla_asystenta_niesie_komplet_parametrow(client, settings):
    """Prompt do wklejenia we własne narzędzie AI musi wystarczyć sam:
    asystent nie ma skąd wziąć adresu, transportu ani sposobu logowania."""
    prompt = _strona(client, settings).context["prompt_dla_asystenta"]

    assert "http://bpp.example.test/mcp" in prompt
    assert "http://bpp.example.test/mcp/auth" in prompt
    assert "Streamable HTTP" in prompt
    assert "OAuth" in prompt
    # Po dodaniu asystent ma sprawdzić, że narzędzia faktycznie są widoczne.
    assert "szukaj_publikacji" in prompt


@pytest.mark.django_db
def test_prompt_jest_na_poczatku_strony_z_przyciskiem_kopiuj(client, settings):
    tresc = _strona(client, settings).content.decode()

    assert 'id="mcp-prompt"' in tresc
    assert 'data-mcp-kopiuj="mcp-prompt"' in tresc
    # „Poproś swoje narzędzie AI” to najprostsza ścieżka — idzie PRZED
    # ręcznymi instrukcjami dla konkretnych klientów.
    assert tresc.index('id="mcp-prompt"') < tresc.index('id="mcp-klienci"')


@pytest.mark.django_db
def test_parametry_serwera(client, settings):
    parametry = dict(_strona(client, settings).context["parametry_serwera"])

    assert parametry["Transport"] == "Streamable HTTP"
    assert parametry["Adres publiczny"] == "http://bpp.example.test/mcp"
    assert parametry["Adres z logowaniem"] == "http://bpp.example.test/mcp/auth"


@pytest.mark.django_db
def test_nazwa_serwera_bez_uczelni(client, settings):
    assert _strona(client, settings).context["nazwa_serwera"] == "bpp"


@pytest.mark.django_db
def test_nazwa_serwera_ze_skrotu_uczelni(client, settings, uczelnia):
    """Kto podłącza bibliografie kilku uczelni, dostaje rozróżnialne nazwy."""
    uczelnia.skrot = "UP Lub"
    uczelnia.save()

    assert _strona(client, settings).context["nazwa_serwera"] == "bpp-up-lub"


@pytest.mark.django_db
def test_instrukcje_klientow_z_linkami_instalacyjnymi(client, settings):
    tresc = _strona(client, settings).content.decode()

    for nazwa in ("ChatGPT", "Claude Code", "OpenAI Codex", "Cursor", "Gemini CLI"):
        assert nazwa in tresc, nazwa
    assert 'href="cursor://anysphere.cursor-deeplink/mcp/install?' in tresc
    assert 'href="https://claude.ai/customize/connectors?' in tresc
    # Każda wklejka dostaje własny przycisk „Kopiuj”.
    assert 'data-mcp-kopiuj="mcp-wklejka-codex-1"' in tresc


@pytest.mark.django_db
def test_link_do_bpp_mcp_dla_stdio(client, settings):
    """Spec §8: link do ``bpp-mcp`` dla klientów bez zdalnego MCP (stdio)."""
    tresc = _strona(client, settings).content.decode()

    assert "https://github.com/iplweb/bpp-mcp" in tresc
