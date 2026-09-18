"""Strona /mcp/ — instrukcja podłączenia dla człowieka."""

import pytest

PUB = "http://bpp.example.test/mcp"
AUTH = "http://bpp.example.test/mcp/auth"


def _strona(client, settings, host="bpp.example.test"):
    # Bez nadpisania ALLOWED_HOSTS Django odda 400 dla obcego Hosta,
    # zanim widok zdąży zbudować adresy (patrz test_cache_vary_host.py).
    settings.ALLOWED_HOSTS = [host]
    odp = client.get("/mcp/", HTTP_HOST=host)
    assert odp.status_code == 200
    return odp


@pytest.mark.django_db
def test_adresy_sa_per_host(client, settings):
    tresc = _strona(client, settings, host="uczelnia1.localhost").content.decode()

    assert "uczelnia1.localhost/mcp" in tresc


@pytest.mark.django_db
def test_certyfikat_ssl_jako_warunek_konieczny(client, admin_client, settings):
    """Niekompletny łańcuch certyfikatów przeglądarka ukryje, klient MCP nie
    — strona ma o tym mówić w obu wariantach, zanim ktoś zacznie klikać."""
    for klient in (client, admin_client):
        tresc = _strona(klient, settings).content.decode()

        assert 'id="mcp-certyfikat"' in tresc
        assert "sine qua non" in tresc
        assert "ssltest/analyze.html?d=bpp.example.test" in tresc
        assert "ssl-checker.html#hostname=bpp.example.test" in tresc


@pytest.mark.django_db
def test_anonim_dostaje_tylko_wariant_publiczny(client, settings):
    """Strona pokazuje JEDEN wariant — dwa przyciski „Dodaj” i pytanie
    „z logowaniem czy bez” myliły. Niezalogowany dostaje publiczny."""
    odp = _strona(client, settings)
    tresc = odp.content.decode()

    assert PUB in tresc
    assert AUTH not in tresc
    prompt = odp.context["prompt_dla_asystenta"]
    assert f"adres: {PUB}" in prompt
    assert "OAuth" not in prompt


@pytest.mark.django_db
def test_anonim_wie_ze_to_nie_pelne_mozliwosci_i_moze_sie_zalogowac(client, settings):
    tresc = _strona(client, settings).content.decode()

    # Zachęta do konta idzie PRZED instrukcjami, żeby nikt jej nie przegapił.
    assert tresc.index('id="mcp-bez-konta"') < tresc.index('id="mcp-prompt"')
    # Wycinek z samą ramką — link logowania ma też górny pasek strony.
    ramka = tresc[tresc.index('id="mcp-bez-konta"') : tresc.index('id="mcp-prompt"')]
    assert "konto" in ramka
    assert "pełnych możliwości" in ramka
    assert 'href="/accounts/login/?next=/mcp/"' in ramka


@pytest.mark.django_db
def test_zalogowany_dostaje_tylko_wariant_z_logowaniem(admin_client, settings):
    """Zalogowany ma konto — dostaje jedną wiadomość do wklejenia, bez wyboru
    wariantu i bez zachęty do zakładania konta."""
    odp = _strona(admin_client, settings)
    tresc = odp.content.decode()

    assert 'id="mcp-bez-konta"' not in tresc
    prompt = odp.context["prompt_dla_asystenta"]
    assert f"adres: {AUTH}" in prompt
    assert "OAuth" in prompt
    assert "Streamable HTTP" in prompt
    # Po dodaniu asystent ma sprawdzić, że narzędzia faktycznie są widoczne.
    assert "szukaj_publikacji" in prompt
    assert dict(odp.context["parametry_serwera"])["Adres"] == AUTH


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
    assert parametry["Adres"] == PUB
    assert parametry["Uwierzytelnianie"] == "brak"


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
    # Każda wklejka kopiuje się kliknięciem w całe pole, nie tylko przyciskiem.
    assert 'data-mcp-kopiuj="mcp-wklejka-codex-1"' in tresc
    assert "mcp-strona__kopiowalny" in tresc
    assert "data-komunikat-ok=" in tresc
    # Oba warianty ścieżki jadą w HTML-u; wybiera strona.js po stronie
    # przeglądarki, bo HTML jest wspólny dla wszystkich systemów.
    assert 'data-system="posix"' in tresc
    assert 'data-system="windows"' in tresc
    assert "%USERPROFILE%\\.cursor\\mcp.json" in tresc


@pytest.mark.django_db
def test_zalogowany_wie_gdzie_dziala_logowanie(admin_client, settings):
    odp = _strona(admin_client, settings)

    assert odp.context["klienci_z_logowaniem"][0] == (
        "Claude (claude.ai, Claude Desktop, Cowork)"
    )
    assert "ChatGPT" in odp.context["klienci_z_logowaniem"]
    assert "Zed" not in odp.context["klienci_z_logowaniem"]
    tresc = odp.content.decode()
    assert "Claude Code" in tresc
    # Klient bez logowania: adres publiczny z wyjaśnieniem, nie błąd DCR.
    assert PUB + "<" in tresc or PUB + "\n" in tresc


@pytest.mark.django_db
def test_link_do_bpp_mcp_dla_stdio(client, settings):
    """Spec §8: link do ``bpp-mcp`` dla klientów bez zdalnego MCP (stdio)."""
    tresc = _strona(client, settings).content.decode()

    assert "https://github.com/iplweb/bpp-mcp" in tresc
