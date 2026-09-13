"""Wklejki i linki instalacyjne strony /mcp/ (bez renderowania HTML).

Formaty linków zweryfikowane w dokumentacji klientów (stan 2026-09):
Claude — ``claude.ai/customize/connectors?modal=add-custom-connector``,
Cursor i LM Studio — ``config`` to base64 z obiektu serwera BEZ nazwy,
VS Code — ``vscode:mcp/install?`` + URL-encoded JSON z nazwą w środku.
"""

import base64
import json
from urllib.parse import parse_qs, unquote, urlsplit

from mcp_server import instrukcje

PUB = "https://bpp.example.test/mcp"
AUTH = "https://bpp.example.test/mcp/auth"

#: Adresy zwrotne tych klientów przechodzą przez allowlistę DCR.
Z_LOGOWANIEM = {"claude", "claude-code", "codex", "gemini-cli", "lm-studio"}


def _klienci():
    return instrukcje.klienci(
        nazwa="bpp-up", adres_publiczny=PUB, adres_z_logowaniem=AUTH
    )


def _klient(slug):
    return next(k for k in _klienci() if k.slug == slug)


def _teksty(klient):
    return "\n".join(
        [w.tekst for w in klient.wklejki] + [link.adres for link in klient.linki]
    )


def _zapytanie(link):
    return {k: v[0] for k, v in parse_qs(urlsplit(link).query).items()}


def _base64_json(wartosc):
    return json.loads(base64.b64decode(wartosc))


def test_link_claude_wypelnia_formularz_konektora():
    link = instrukcje.link_claude("bpp-up", AUTH)

    assert link.startswith("https://claude.ai/customize/connectors?")
    assert _zapytanie(link) == {
        "modal": "add-custom-connector",
        "connectorName": "bpp-up",
        "connectorUrl": AUTH,
    }


def test_link_cursor_koduje_obiekt_serwera_bez_nazwy():
    link = instrukcje.link_cursor("bpp-up", PUB)

    assert link.startswith("cursor://anysphere.cursor-deeplink/mcp/install?")
    zapytanie = _zapytanie(link)
    assert zapytanie["name"] == "bpp-up"
    assert _base64_json(zapytanie["config"]) == {"url": PUB}
    # „=” z paddingu base64 nie może zostać surowe w query stringu.
    assert "=" not in link.split("config=", 1)[1]


def test_link_lmstudio_koduje_obiekt_serwera_bez_nazwy():
    link = instrukcje.link_lmstudio("bpp-up", PUB)

    assert link.startswith("lmstudio://add_mcp?")
    zapytanie = _zapytanie(link)
    assert zapytanie["name"] == "bpp-up"
    assert _base64_json(zapytanie["config"]) == {"url": PUB}


def test_link_vscode_niesie_nazwe_typ_i_adres():
    link = instrukcje.link_vscode("bpp-up", AUTH)

    przedrostek = "vscode:mcp/install?"
    assert link.startswith(przedrostek)
    assert json.loads(unquote(link[len(przedrostek) :])) == {
        "name": "bpp-up",
        "type": "http",
        "url": AUTH,
    }


def test_kazdy_klient_ma_tresc_i_unikalne_identyfikatory():
    klienci = _klienci()

    slugi = [k.slug for k in klienci]
    assert len(slugi) == len(set(slugi))
    id_wklejek = [w.id for k in klienci for w in k.wklejki]
    assert len(id_wklejek) == len(set(id_wklejek))
    for klient in klienci:
        assert klient.kroki or klient.wklejki or klient.linki, klient.slug


def test_oczekiwani_klienci_sa_na_liscie():
    slugi = {k.slug for k in _klienci()}

    assert {
        "claude",
        "chatgpt",
        "claude-code",
        "codex",
        "cursor",
        "vscode",
        "gemini-cli",
        "windsurf",
        "zed",
        "lm-studio",
    } <= slugi


def test_logowanie_tylko_tam_gdzie_adres_zwrotny_przejdzie_przez_dcr():
    """Allowlista ``redirect_uri`` w DCR wpuszcza Claude i loopback. Wariant
    z logowaniem u innych klientów kończyłby się ``invalid_redirect_uri``,
    więc strona nie może go podsuwać."""
    assert {k.slug for k in _klienci() if k.logowanie} == Z_LOGOWANIEM


def test_klient_z_logowaniem_dostaje_oba_warianty():
    for klient in _klienci():
        if not klient.logowanie:
            continue
        teksty = _teksty(klient)
        assert PUB in teksty or klient.linki, klient.slug
        assert AUTH in teksty or len(klient.linki) == 2, klient.slug


def test_klient_bez_logowania_dostaje_tylko_dostep_publiczny_i_wyjasnienie():
    for klient in _klienci():
        if klient.logowanie:
            continue
        assert AUTH not in _teksty(klient), klient.slug
        assert len(klient.linki) <= 1, klient.slug
        assert any("dostępu publicznego" in u for u in klient.uwagi), klient.slug


def test_logowanie_wynika_z_allowlisty_dcr(monkeypatch):
    """Rozszerzenie allowlisty (np. o chatgpt.com) ma samo odblokować wariant
    z logowaniem na stronie — bez drugiej, ręcznie utrzymywanej listy."""
    monkeypatch.setattr(instrukcje, "dozwolony_redirect_uri", lambda uri: True)

    assert _klient("chatgpt").logowanie
    assert AUTH in _teksty(_klient("chatgpt"))


def test_codex_loguje_sie_osobnym_poleceniem():
    teksty = _teksty(_klient("codex"))

    assert f"codex mcp add bpp-up --url {AUTH}" in teksty
    assert "codex mcp login bpp-up" in teksty


def test_claude_code_z_zakresem_uzytkownika():
    teksty = _teksty(_klient("claude-code"))

    assert f"claude mcp add --transport http --scope user bpp-up {PUB}" in teksty


def test_gemini_uzywa_transportu_http():
    teksty = _teksty(_klient("gemini-cli"))

    assert f"gemini mcp add --transport http --scope user bpp-up {PUB}" in teksty


def test_liczba_linkow_instalacyjnych_zalezy_od_logowania():
    assert len(_klient("claude").linki) == 2
    assert len(_klient("lm-studio").linki) == 2
    assert len(_klient("cursor").linki) == 1
    assert len(_klient("vscode").linki) == 1


def test_prompt_podpowiada_wariant_publiczny_przy_odrzuconej_rejestracji():
    prompt = instrukcje.prompt_dla_asystenta(
        nazwa="bpp-up", adres_publiczny=PUB, adres_z_logowaniem=AUTH
    )

    assert "invalid_redirect_uri" in prompt
