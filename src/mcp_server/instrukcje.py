"""Treść strony ``/mcp/``: prompt dla asystenta AI, parametry, wklejki klientów.

Czyste funkcje bez requestu — widok podaje adresy i uczelnię, szablon tylko
wyświetla. Dzięki temu prompt, linki i wklejki są testowalne bez HTML.

Kroki i formaty linków instalacyjnych zweryfikowane w dokumentacji klientów
(stan 2026-09). Klienci zmieniają nazwy menu często — przy zgłoszeniu
„nie ma takiej opcji” zacznij od sprawdzenia ich aktualnej dokumentacji.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from django.utils.text import slugify
from django.utils.translation import gettext as _

#: Po tych narzędziach asystent pozna, że serwer faktycznie się podłączył.
NARZEDZIA_KONTROLNE = ("szukaj_publikacji", "szukaj_autora")

#: Lokalny serwer (stdio) dla klientów bez obsługi zdalnego MCP.
ADRES_BPP_MCP = "https://github.com/iplweb/bpp-mcp"

TRANSPORT = "Streamable HTTP"


def nazwa_serwera(uczelnia) -> str:
    """Nazwa serwera w kliencie: ``bpp-<skrót uczelni>`` albo ``bpp``.

    Kto podłącza bibliografie kilku uczelni, dostaje rozróżnialne wpisy.
    ``slugify`` gubi ``ł`` (nie rozkłada się w NFKD), stąd ręczna zamiana.
    """
    if uczelnia is None:
        return "bpp"
    skrot = uczelnia.skrot.replace("ł", "l").replace("Ł", "L")
    slug = slugify(skrot)
    return f"bpp-{slug}" if slug else "bpp"


def prompt_dla_asystenta(
    *, nazwa: str, adres_publiczny: str, adres_z_logowaniem: str
) -> str:
    """Wiadomość do wklejenia we własne narzędzie AI — musi wystarczyć sama."""
    return _(
        "Dodaj, proszę, zdalny serwer MCP z bibliografią publikacji do "
        "programu, w którym teraz rozmawiamy.\n"
        "\n"
        "Wariant publiczny (bez logowania, dane publiczne):\n"
        "- nazwa: %(nazwa)s\n"
        "- transport: %(transport)s\n"
        "- adres: %(publiczny)s\n"
        "- uwierzytelnianie: brak\n"
        "\n"
        "Wariant z logowaniem (także dane niepubliczne, dla osób z kontem "
        "w bibliografii):\n"
        "- nazwa: %(nazwa)s\n"
        "- transport: %(transport)s\n"
        "- adres: %(z_logowaniem)s\n"
        "- uwierzytelnianie: OAuth 2.1 z dynamiczną rejestracją klienta (DCR) "
        "i PKCE; logowanie odbywa się w przeglądarce, nie podawaj klucza API "
        "ani hasła\n"
        "\n"
        "Oba warianty dają dostęp tylko do odczytu.\n"
        "\n"
        "Zanim zaczniesz, zapytaj mnie, którego wariantu chcę. Jeśli potrafisz "
        "dodać serwer sam (poleceniem w terminalu albo edycją pliku "
        "konfiguracyjnego), zrób to i pokaż, co zmieniasz. Jeśli nie — podaj "
        "mi dokładne kroki w ustawieniach tego programu. Na koniec sprawdź, "
        "czy widać narzędzia %(narzedzia)s."
    ) % {
        "nazwa": nazwa,
        "transport": TRANSPORT,
        "publiczny": adres_publiczny,
        "z_logowaniem": adres_z_logowaniem,
        "narzedzia": ", ".join(NARZEDZIA_KONTROLNE),
    }


def parametry_serwera(
    *, nazwa: str, adres_publiczny: str, adres_z_logowaniem: str
) -> list[tuple[str, str]]:
    return [
        (_("Nazwa"), nazwa),
        (_("Transport"), TRANSPORT),
        (_("Adres publiczny"), adres_publiczny),
        (_("Adres z logowaniem"), adres_z_logowaniem),
        (
            _("Uwierzytelnianie"),
            _("brak (adres publiczny); OAuth 2.1 z DCR i PKCE (adres z logowaniem)"),
        ),
        (_("Uprawnienia"), _("tylko odczyt")),
    ]


# --- Linki instalacyjne ------------------------------------------------------


def _base64_json(obiekt: dict) -> str:
    return base64.b64encode(json.dumps(obiekt, separators=(",", ":")).encode()).decode()


def link_claude(nazwa: str, adres: str) -> str:
    """Otwiera claude.ai z wypełnionym formularzem własnego konektora."""
    return "https://claude.ai/customize/connectors?" + urlencode(
        {
            "modal": "add-custom-connector",
            "connectorName": nazwa,
            "connectorUrl": adres,
        }
    )


def link_cursor(nazwa: str, adres: str) -> str:
    """``config`` to base64 z obiektu serwera BEZ nazwy (nazwa idzie w ``name``)."""
    return "cursor://anysphere.cursor-deeplink/mcp/install?" + urlencode(
        {"name": nazwa, "config": _base64_json({"url": adres})}
    )


def link_lmstudio(nazwa: str, adres: str) -> str:
    """Ten sam układ co w Cursorze: ``name`` + base64 z obiektu serwera."""
    return "lmstudio://add_mcp?" + urlencode(
        {"name": nazwa, "config": _base64_json({"url": adres})}
    )


def link_vscode(nazwa: str, adres: str) -> str:
    """``vscode:mcp/install?`` + URL-encoded JSON z nazwą W ŚRODKU obiektu."""
    obiekt = {"name": nazwa, "type": "http", "url": adres}
    return "vscode:mcp/install?" + quote(
        json.dumps(obiekt, separators=(",", ":")), safe=""
    )


# --- Klienci -----------------------------------------------------------------


@dataclass(frozen=True)
class Link:
    etykieta: str
    adres: str

    @property
    def zewnetrzny(self) -> bool:
        """Strona WWW (nowa karta), a nie schemat aplikacji (``cursor://``)."""
        return self.adres.startswith("https://")


@dataclass(frozen=True)
class Wklejka:
    id: str
    opis: str
    tekst: str


@dataclass(frozen=True)
class Klient:
    """Instrukcja podłączenia dla jednego narzędzia AI."""

    slug: str
    nazwa: str
    linki: tuple[Link, ...] = ()
    kroki: tuple[str, ...] = ()
    wklejki: tuple[Wklejka, ...] = ()
    uwagi: tuple[str, ...] = ()


def _klient(slug, nazwa, *, linki=(), kroki=(), wklejki=(), uwagi=()):
    """Złóż klienta, nadając wklejkom identyfikatory unikalne na stronie."""
    return Klient(
        slug=slug,
        nazwa=nazwa,
        linki=tuple(linki),
        kroki=tuple(kroki),
        wklejki=tuple(
            Wklejka(id=f"mcp-wklejka-{slug}-{nr}", opis=opis, tekst=tekst)
            for nr, (opis, tekst) in enumerate(wklejki, start=1)
        ),
        uwagi=tuple(uwagi),
    )


def _json(obiekt: dict) -> str:
    return json.dumps(obiekt, indent=2, ensure_ascii=False)


def klienci(*, nazwa: str, adres_publiczny: str, adres_z_logowaniem: str):
    pub, auth = adres_publiczny, adres_z_logowaniem
    publiczny, z_logowaniem = _("Dostęp publiczny"), _("Dostęp z logowaniem")

    def linki(generator):
        return [
            Link(_("Dodaj — dostęp publiczny"), generator(nazwa, pub)),
            Link(_("Dodaj — z logowaniem"), generator(nazwa, auth)),
        ]

    def adresy():
        return [
            (_("Adres — dostęp publiczny"), pub),
            (_("Adres — dostęp z logowaniem"), auth),
        ]

    def pary(opis_pliku, budowniczy):
        return [
            (f"{opis_pliku} — {publiczny.lower()}", budowniczy(pub)),
            (f"{opis_pliku} — {z_logowaniem.lower()}", budowniczy(auth)),
        ]

    return [
        _klient(
            "claude",
            "Claude (claude.ai, Claude Desktop, Cowork)",
            linki=linki(link_claude),
            kroki=[
                _(
                    "Albo ręcznie: w Claude otwórz Customize → Connectors, "
                    "kliknij „+” i wybierz Add custom connector."
                ),
                _("Wpisz nazwę %(nazwa)s i adres serwera, potem kliknij Add.")
                % {"nazwa": nazwa},
            ],
            wklejki=adresy(),
            uwagi=[
                _(
                    "Konektor dodajesz raz — działa w claude.ai, Claude Desktop, "
                    "Cowork i aplikacji mobilnej."
                ),
                _(
                    "W planach Team i Enterprise konektor najpierw dodaje "
                    "właściciel organizacji (Organization settings → "
                    "Connectors), a członkowie tylko go łączą. W planie Free "
                    "można dodać jeden własny konektor."
                ),
                _(
                    "Claude łączy się z serwerem z chmury Anthropic, więc adres "
                    "musi być dostępny z internetu."
                ),
            ],
        ),
        _klient(
            "chatgpt",
            "ChatGPT",
            kroki=[
                _(
                    "W ChatGPT w przeglądarce otwórz ustawienia i włącz tryb "
                    "deweloperski (Developer mode) — obecnie w sekcji Security "
                    "and login."
                ),
                _(
                    "W ustawieniach aplikacji kliknij „+”, utwórz nową aplikację "
                    "i podaj nazwę %(nazwa)s oraz adres serwera."
                )
                % {"nazwa": nazwa},
                _(
                    "W rozmowie wybierz z menu „+” Developer mode i zaznacz "
                    "dodaną aplikację."
                ),
            ],
            wklejki=adresy(),
            uwagi=[
                _(
                    "Wymaga planu Plus, Pro, Business, Enterprise lub Edu. "
                    "Nazwy pozycji menu ChatGPT często się zmieniają — "
                    "w razie wątpliwości szukaj „Developer mode”."
                ),
            ],
        ),
        _klient(
            "claude-code",
            "Claude Code",
            wklejki=[
                (
                    publiczny,
                    f"claude mcp add --transport http --scope user {nazwa} {pub}",
                ),
                (
                    z_logowaniem,
                    f"claude mcp add --transport http --scope user {nazwa} {auth}\n"
                    f"claude mcp login {nazwa}",
                ),
            ],
            uwagi=[
                _(
                    "--scope user udostępnia serwer we wszystkich projektach. "
                    "Zamiast claude mcp login możesz w sesji wpisać /mcp "
                    "i wybrać serwer."
                ),
            ],
        ),
        _klient(
            "codex",
            "OpenAI Codex",
            wklejki=[
                (publiczny, f"codex mcp add {nazwa} --url {pub}"),
                (
                    z_logowaniem,
                    f"codex mcp add {nazwa} --url {auth}\n"
                    f"codex mcp login {nazwa} --scopes read",
                ),
                (
                    _("Albo wpis w ~/.codex/config.toml"),
                    f'[mcp_servers.{nazwa}]\nurl = "{pub}"',
                ),
            ],
            uwagi=[
                _(
                    "Ta sama konfiguracja działa w Codex CLI, rozszerzeniu do "
                    "edytora i aplikacji desktopowej."
                ),
            ],
        ),
        _klient(
            "cursor",
            "Cursor",
            linki=linki(link_cursor),
            wklejki=pary(
                "~/.cursor/mcp.json",
                lambda adres: _json({"mcpServers": {nazwa: {"url": adres}}}),
            ),
            uwagi=[
                _(
                    "Przy adresie z logowaniem Cursor sam otworzy przeglądarkę "
                    "do zalogowania."
                ),
            ],
        ),
        _klient(
            "vscode",
            "Visual Studio Code (GitHub Copilot)",
            linki=linki(link_vscode),
            wklejki=pary(
                _("Polecenie"),
                lambda adres: (
                    "code --add-mcp '"
                    + json.dumps(
                        {"name": nazwa, "type": "http", "url": adres},
                        separators=(",", ":"),
                    )
                    + "'"
                ),
            ),
            uwagi=[
                _(
                    "Narzędzia serwera są dostępne w trybie agenta GitHub "
                    "Copilot. Przy adresie z logowaniem VS Code poprosi "
                    "o zalogowanie."
                ),
            ],
        ),
        _klient(
            "gemini-cli",
            "Gemini CLI",
            wklejki=pary(
                _("Polecenie"),
                lambda adres: (
                    f"gemini mcp add --transport http --scope user {nazwa} {adres}"
                ),
            ),
            uwagi=[
                _(
                    "Przy adresie z logowaniem uruchom w sesji Gemini CLI "
                    "polecenie /mcp auth %(nazwa)s."
                )
                % {"nazwa": nazwa},
            ],
        ),
        _klient(
            "windsurf",
            "Windsurf",
            wklejki=pary(
                "~/.codeium/windsurf/mcp_config.json",
                lambda adres: _json({"mcpServers": {nazwa: {"serverUrl": adres}}}),
            ),
        ),
        _klient(
            "zed",
            "Zed",
            kroki=[
                _(
                    "Otwórz Settings → AI → MCP Servers i kliknij Add Remote "
                    "Server — albo dopisz wpis do settings.json."
                ),
            ],
            wklejki=pary(
                "settings.json",
                lambda adres: _json({"context_servers": {nazwa: {"url": adres}}}),
            ),
            uwagi=[_("Przy adresie z logowaniem Zed sam uruchomi logowanie.")],
        ),
        _klient(
            "lm-studio",
            "LM Studio",
            linki=linki(link_lmstudio),
            wklejki=pary(
                "mcp.json",
                lambda adres: _json({"mcpServers": {nazwa: {"url": adres}}}),
            ),
            uwagi=[_("Wymaga LM Studio w wersji 0.3.17 lub nowszej.")],
        ),
        _klient(
            "le-chat",
            "Mistral Le Chat",
            kroki=[
                _(
                    "W Le Chat otwórz Intelligence → Connectors i kliknij Add Connector."
                ),
                _(
                    "Na karcie Custom MCP Connector podaj nazwę %(nazwa)s "
                    "i adres serwera."
                )
                % {"nazwa": nazwa},
            ],
            wklejki=adresy(),
        ),
        _klient(
            "copilot-studio",
            "Microsoft Copilot Studio",
            kroki=[
                _(
                    "Otwórz agenta i przejdź do Tools → Add a tool → New tool "
                    "→ Model Context Protocol."
                ),
                _(
                    "Podaj nazwę %(nazwa)s, krótki opis i adres serwera. Dla "
                    "adresu z logowaniem wybierz OAuth 2.0 z opcją Dynamic "
                    "discovery."
                )
                % {"nazwa": nazwa},
            ],
            wklejki=adresy(),
            uwagi=[
                _(
                    "W Microsoft 365 Copilot własny serwer MCP rejestruje "
                    "administrator."
                ),
            ],
        ),
    ]
