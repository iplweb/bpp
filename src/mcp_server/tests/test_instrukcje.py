"""Wklejki i linki instalacyjne strony /mcp/ (bez bazy, bez renderowania).

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


def _klienci():
    return instrukcje.klienci(
        nazwa="bpp-up", adres_publiczny=PUB, adres_z_logowaniem=AUTH
    )


def _klient(slug):
    return next(k for k in _klienci() if k.slug == slug)


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


def test_wklejki_maja_warianty_publiczny_i_z_logowaniem():
    """Ręczne wklejki nie wymagają przerabiania adresu: każda jest w obu
    wariantach, a wariant z logowaniem niesie adres ``/mcp/auth``."""
    for klient in _klienci():
        if not klient.wklejki:
            continue
        teksty = "\n".join(w.tekst for w in klient.wklejki)
        assert PUB in teksty, klient.slug
        assert AUTH in teksty, klient.slug


def test_codex_loguje_sie_osobnym_poleceniem():
    teksty = "\n".join(w.tekst for w in _klient("codex").wklejki)

    assert f"codex mcp add bpp-up --url {AUTH}" in teksty
    assert "codex mcp login bpp-up" in teksty


def test_claude_code_z_zakresem_uzytkownika():
    teksty = "\n".join(w.tekst for w in _klient("claude-code").wklejki)

    assert f"claude mcp add --transport http --scope user bpp-up {PUB}" in teksty


def test_gemini_uzywa_transportu_http():
    teksty = "\n".join(w.tekst for w in _klient("gemini-cli").wklejki)

    assert f"gemini mcp add --transport http --scope user bpp-up {PUB}" in teksty


def test_linki_instalacyjne_w_obu_wariantach():
    for slug in ("claude", "cursor", "vscode", "lm-studio"):
        adresy = " ".join(link.adres for link in _klient(slug).linki)
        # Linki kodują adres (base64 / URL-encoding) — sprawdzamy liczbę
        # wariantów, a poprawność kodowania pokrywają testy link_*.
        assert len(_klient(slug).linki) == 2, slug
        assert adresy, slug
