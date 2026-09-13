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

from oauth_mcp.views_dcr import dozwolony_redirect_uri

#: Po tych narzędziach asystent pozna, że serwer faktycznie się podłączył.
NARZEDZIA_KONTROLNE = ("szukaj_publikacji", "szukaj_autora")

#: Lokalny serwer (stdio) dla klientów bez obsługi zdalnego MCP.
ADRES_BPP_MCP = "https://github.com/iplweb/bpp-mcp"

TRANSPORT = "Streamable HTTP"

#: Adresy zwrotne OAuth, które klient zgłasza przy dynamicznej rejestracji
#: (DCR) — z dokumentacji klientów, stan 2026-09. Rejestracja w ``oauth_mcp``
#: odrzuca klienta, gdy CHOĆ JEDEN adres nie przejdzie przez allowlistę, więc
#: wariant z logowaniem pokazujemy tylko, gdy przechodzą wszystkie. Klient
#: spoza słownika (adres nieznany) dostaje wyłącznie dostęp publiczny.
#:
#: Klienci CLI słuchają na pętli zwrotnej z losowym portem; allowlista
#: przepuszcza dowolny port i ścieżkę na localhost/127.0.0.1, więc port
#: i ścieżka poniżej są tylko przykładowe.
ADRESY_ZWROTNE = {
    "claude": ("https://claude.ai/api/mcp/auth_callback",),
    "chatgpt": ("https://chatgpt.com/connector_platform_oauth_redirect",),
    "claude-code": ("http://localhost:33418/callback",),
    "codex": ("http://127.0.0.1:33418/callback",),
    "vscode": ("http://127.0.0.1:33418/", "https://vscode.dev/redirect"),
    "gemini-cli": ("http://localhost:33418/oauth/callback",),
    "lm-studio": ("http://127.0.0.1:33389/mcp-oauth-callback",),
}


def obsluguje_logowanie(slug: str) -> bool:
    """Czy klient przejdzie rejestrację DCR (a więc adres ``/mcp/auth``)."""
    adresy = ADRESY_ZWROTNE.get(slug, ())
    return bool(adresy) and all(dozwolony_redirect_uri(a) for a in adresy)


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
        "mi dokładne kroki w ustawieniach tego programu. Jeśli rejestracja "
        "klienta OAuth zostanie odrzucona (np. błąd invalid_redirect_uri), ten "
        "program nie obsługuje logowania do tej bibliografii — użyj wtedy "
        "wariantu publicznego. Na koniec sprawdź, czy widać narzędzia "
        "%(narzedzia)s."
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
    logowanie: bool = False
    linki: tuple[Link, ...] = ()
    kroki: tuple[str, ...] = ()
    wklejki: tuple[Wklejka, ...] = ()
    uwagi: tuple[str, ...] = ()


def _klient(slug, nazwa, *, linki=(), kroki=(), wklejki=(), uwagi=()):
    """Złóż klienta: identyfikatory wklejek i uwaga, gdy nie ma logowania."""
    logowanie = obsluguje_logowanie(slug)
    uwagi = list(uwagi)
    if not logowanie:
        uwagi.append(
            _(
                "Logowanie (adres z /mcp/auth) nie jest w tym narzędziu "
                "obsługiwane albo nie zostało jeszcze sprawdzone — korzystaj "
                "z dostępu publicznego."
            )
        )
    return Klient(
        slug=slug,
        nazwa=nazwa,
        logowanie=logowanie,
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

    def warianty(slug, opis_publiczny, opis_z_logowaniem, budowniczy):
        """Wariant publiczny, a z logowaniem tylko, gdy klient go obsłuży."""
        wynik = [(opis_publiczny, budowniczy(pub))]
        if obsluguje_logowanie(slug):
            wynik.append((opis_z_logowaniem, budowniczy(auth)))
        return wynik

    def linki(slug, generator):
        return [
            Link(etykieta, adres)
            for etykieta, adres in warianty(
                slug,
                _("Dodaj — dostęp publiczny"),
                _("Dodaj — z logowaniem"),
                lambda adres: generator(nazwa, adres),
            )
        ]

    def adresy(slug):
        return warianty(
            slug,
            _("Adres — dostęp publiczny"),
            _("Adres — dostęp z logowaniem"),
            lambda adres: adres,
        )

    def pary(slug, opis_pliku, budowniczy):
        return warianty(
            slug,
            f"{opis_pliku} — {publiczny.lower()}",
            f"{opis_pliku} — {z_logowaniem.lower()}",
            budowniczy,
        )

    def z_loginem(polecenie, adres, logowanie):
        """Dopisz polecenie logowania do wklejki z adresem ``/mcp/auth``."""
        return f"{polecenie}\n{logowanie}" if adres == auth else polecenie

    return [
        _klient(
            "claude",
            "Claude (claude.ai, Claude Desktop, Cowork)",
            linki=linki("claude", link_claude),
            kroki=[
                _(
                    "Albo ręcznie: w Claude otwórz Customize → Connectors, "
                    "kliknij „+” i wybierz Add custom connector."
                ),
                _("Wpisz nazwę %(nazwa)s i adres serwera, potem kliknij Add.")
                % {"nazwa": nazwa},
            ],
            wklejki=adresy("claude"),
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
            wklejki=adresy("chatgpt"),
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
            wklejki=warianty(
                "claude-code",
                publiczny,
                z_logowaniem,
                lambda adres: z_loginem(
                    f"claude mcp add --transport http --scope user {nazwa} {adres}",
                    adres,
                    f"claude mcp login {nazwa}",
                ),
            ),
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
                *warianty(
                    "codex",
                    publiczny,
                    z_logowaniem,
                    lambda adres: z_loginem(
                        f"codex mcp add {nazwa} --url {adres}",
                        adres,
                        f"codex mcp login {nazwa} --scopes read",
                    ),
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
            linki=linki("cursor", link_cursor),
            wklejki=pary(
                "cursor",
                "~/.cursor/mcp.json",
                lambda adres: _json({"mcpServers": {nazwa: {"url": adres}}}),
            ),
        ),
        _klient(
            "vscode",
            "Visual Studio Code (GitHub Copilot)",
            linki=linki("vscode", link_vscode),
            wklejki=pary(
                "vscode",
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
                _("Narzędzia serwera są dostępne w trybie agenta GitHub Copilot."),
            ],
        ),
        _klient(
            "gemini-cli",
            "Gemini CLI",
            wklejki=pary(
                "gemini-cli",
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
                "windsurf",
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
                "zed",
                "settings.json",
                lambda adres: _json({"context_servers": {nazwa: {"url": adres}}}),
            ),
        ),
        _klient(
            "lm-studio",
            "LM Studio",
            linki=linki("lm-studio", link_lmstudio),
            wklejki=pary(
                "lm-studio",
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
                    "W Le Chat otwórz Intelligence → Connectors i kliknij Add "
                    "Connector."
                ),
                _(
                    "Na karcie Custom MCP Connector podaj nazwę %(nazwa)s "
                    "i adres serwera."
                )
                % {"nazwa": nazwa},
            ],
            wklejki=adresy("le-chat"),
        ),
        _klient(
            "copilot-studio",
            "Microsoft Copilot Studio",
            kroki=[
                _(
                    "Otwórz agenta i przejdź do Tools → Add a tool → New tool "
                    "→ Model Context Protocol."
                ),
                _("Podaj nazwę %(nazwa)s, krótki opis i adres serwera.")
                % {"nazwa": nazwa},
            ],
            wklejki=adresy("copilot-studio"),
            uwagi=[
                _(
                    "W Microsoft 365 Copilot własny serwer MCP rejestruje "
                    "administrator."
                ),
            ],
        ),
    ]
