"""Treść strony ``/mcp/``: prompt dla asystenta AI, parametry, wklejki klientów.

Czyste funkcje bez requestu — widok podaje adresy i uczelnię, szablon tylko
wyświetla. Dzięki temu prompt, linki i wklejki są testowalne bez HTML.

Strona pokazuje JEDEN wariant naraz: zalogowanemu — dostęp z logowaniem,
pozostałym — dostęp publiczny. Dwa przyciski „Dodaj” obok siebie i prompt
każący asystentowi dopytywać „z logowaniem czy bez” myliły użytkowników.

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


# --- Prompt dla asystenta ----------------------------------------------------


def _uwierzytelnianie(z_logowaniem: bool) -> str:
    if z_logowaniem:
        return _(
            "OAuth 2.1 z dynamiczną rejestracją klienta (DCR) i PKCE; logowanie "
            "odbywa się w przeglądarce, nie podawaj klucza API ani hasła"
        )
    return _("brak")


def _parametry_w_prompcie(*, nazwa: str, adres: str, z_logowaniem: bool) -> str:
    return _(
        "- nazwa: %(nazwa)s\n"
        "- transport: %(transport)s\n"
        "- adres: %(adres)s\n"
        "- uwierzytelnianie: %(uwierzytelnianie)s\n"
    ) % {
        "nazwa": nazwa,
        "transport": TRANSPORT,
        "adres": adres,
        "uwierzytelnianie": _uwierzytelnianie(z_logowaniem),
    }


def _jak_dodac() -> str:
    return _(
        "Jeśli potrafisz dodać serwer sam (poleceniem w terminalu albo edycją "
        "pliku konfiguracyjnego), zrób to i pokaż, co zmieniasz. Jeśli nie — "
        "podaj mi dokładne kroki w ustawieniach tego programu."
    )


def _sprawdz_narzedzia() -> str:
    return _("Na koniec sprawdź, czy widać narzędzia %(narzedzia)s.") % {
        "narzedzia": ", ".join(NARZEDZIA_KONTROLNE)
    }


def prompt_z_logowaniem(
    *, nazwa: str, adres_publiczny: str, adres_z_logowaniem: str
) -> str:
    """Wiadomość dla osoby z kontem — podłącza od razu dostęp z logowaniem.

    Adres publiczny pada tylko jako plan awaryjny: klient spoza allowlisty
    DCR dostanie ``invalid_redirect_uri`` i asystent ma się wtedy cofnąć sam,
    bez dopytywania użytkownika.
    """
    return "".join(
        [
            _(
                "Dodaj, proszę, zdalny serwer MCP z bibliografią publikacji do "
                "programu, w którym teraz rozmawiamy. Mam konto w tej "
                "bibliografii, więc podłącz dostęp z logowaniem:\n"
            ),
            "\n",
            _parametry_w_prompcie(
                nazwa=nazwa, adres=adres_z_logowaniem, z_logowaniem=True
            ),
            "\n",
            _("Serwer daje dostęp tylko do odczytu."),
            "\n\n",
            _jak_dodac(),
            " ",
            _(
                "Jeśli rejestracja klienta OAuth zostanie odrzucona (np. błąd "
                "invalid_redirect_uri), ten program nie obsługuje logowania do "
                "tej bibliografii — dodaj wtedy serwer bez uwierzytelniania pod "
                "adresem %(adres)s (tylko dane publiczne) i powiedz mi o tym."
            )
            % {"adres": adres_publiczny},
            " ",
            _sprawdz_narzedzia(),
        ]
    )


def prompt_publiczny(*, nazwa: str, adres_publiczny: str) -> str:
    """Wiadomość dla osoby bez konta — tylko dostęp publiczny, bez logowania."""
    return "".join(
        [
            _(
                "Dodaj, proszę, zdalny serwer MCP z bibliografią publikacji do "
                "programu, w którym teraz rozmawiamy:\n"
            ),
            "\n",
            _parametry_w_prompcie(
                nazwa=nazwa, adres=adres_publiczny, z_logowaniem=False
            ),
            "\n",
            _(
                "Serwer daje dostęp tylko do odczytu i tylko do publicznej "
                "części bibliografii."
            ),
            "\n\n",
            _jak_dodac(),
            " ",
            _sprawdz_narzedzia(),
        ]
    )


def parametry_serwera(
    *, nazwa: str, adres: str, z_logowaniem: bool
) -> list[tuple[str, str]]:
    return [
        (_("Nazwa"), nazwa),
        (_("Transport"), TRANSPORT),
        (_("Adres"), adres),
        (_("Uwierzytelnianie"), _uwierzytelnianie(z_logowaniem)),
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


def _json(obiekt: dict) -> str:
    return json.dumps(obiekt, indent=2, ensure_ascii=False)


def klienci(
    *,
    nazwa: str,
    adres_publiczny: str,
    adres_z_logowaniem: str,
    z_logowaniem: bool,
):
    """Instrukcje klientów w jednym wariancie — jeden przycisk, jeden adres.

    W wariancie z logowaniem klient spoza allowlisty DCR i tak dostaje adres
    publiczny (logowanie skończyłoby się ``invalid_redirect_uri``) i uwagę,
    dlaczego.
    """

    def adres(slug):
        if z_logowaniem and obsluguje_logowanie(slug):
            return adres_z_logowaniem
        return adres_publiczny

    def klient(slug, nazwa_klienta, *, linki=(), kroki=(), wklejki=(), uwagi=()):
        """Złóż klienta: identyfikatory wklejek i uwaga, gdy nie ma logowania."""
        logowanie = obsluguje_logowanie(slug)
        uwagi = list(uwagi)
        if z_logowaniem and not logowanie:
            uwagi.append(
                _(
                    "To narzędzie nie obsługuje logowania do tej bibliografii "
                    "(albo nie zostało to jeszcze sprawdzone) — podłączysz je "
                    "tylko jako dostęp publiczny, bez danych niepublicznych."
                )
            )
        return Klient(
            slug=slug,
            nazwa=nazwa_klienta,
            logowanie=logowanie,
            linki=tuple(Link(_("Dodaj serwer"), link) for link in linki),
            kroki=tuple(kroki),
            wklejki=tuple(
                Wklejka(id=f"mcp-wklejka-{slug}-{nr}", opis=opis, tekst=tekst)
                for nr, (opis, tekst) in enumerate(wklejki, start=1)
            ),
            uwagi=tuple(uwagi),
        )

    def z_loginem(polecenie, slug, logowanie):
        """Dopisz polecenie logowania, gdy klient dostał adres ``/mcp/auth``."""
        if adres(slug) == adres_z_logowaniem:
            return f"{polecenie}\n{logowanie}"
        return polecenie

    adres_serwera = _("Adres serwera")
    polecenie = _("Polecenie")

    return [
        klient(
            "claude",
            "Claude (claude.ai, Claude Desktop, Cowork)",
            linki=[link_claude(nazwa, adres("claude"))],
            kroki=[
                _(
                    "Albo ręcznie: w Claude otwórz Customize → Connectors, "
                    "kliknij „+” i wybierz Add custom connector."
                ),
                _("Wpisz nazwę %(nazwa)s i adres serwera, potem kliknij Add.")
                % {"nazwa": nazwa},
            ],
            wklejki=[(adres_serwera, adres("claude"))],
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
        klient(
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
            wklejki=[(adres_serwera, adres("chatgpt"))],
            uwagi=[
                _(
                    "Wymaga planu Plus, Pro, Business, Enterprise lub Edu. "
                    "Nazwy pozycji menu ChatGPT często się zmieniają — "
                    "w razie wątpliwości szukaj „Developer mode”."
                ),
            ],
        ),
        klient(
            "claude-code",
            "Claude Code",
            wklejki=[
                (
                    polecenie,
                    z_loginem(
                        "claude mcp add --transport http --scope user "
                        f"{nazwa} {adres('claude-code')}",
                        "claude-code",
                        f"claude mcp login {nazwa}",
                    ),
                )
            ],
            uwagi=[
                _("--scope user udostępnia serwer we wszystkich projektach."),
                *(
                    [
                        _(
                            "Zamiast claude mcp login możesz w sesji wpisać /mcp "
                            "i wybrać serwer."
                        )
                    ]
                    if adres("claude-code") == adres_z_logowaniem
                    else []
                ),
            ],
        ),
        klient(
            "codex",
            "OpenAI Codex",
            wklejki=[
                (
                    polecenie,
                    z_loginem(
                        f"codex mcp add {nazwa} --url {adres('codex')}",
                        "codex",
                        f"codex mcp login {nazwa} --scopes read",
                    ),
                ),
                (
                    _("Albo wpis w ~/.codex/config.toml"),
                    f'[mcp_servers.{nazwa}]\nurl = "{adres("codex")}"',
                ),
            ],
            uwagi=[
                _(
                    "Ta sama konfiguracja działa w Codex CLI, rozszerzeniu do "
                    "edytora i aplikacji desktopowej."
                ),
            ],
        ),
        klient(
            "cursor",
            "Cursor",
            linki=[link_cursor(nazwa, adres("cursor"))],
            wklejki=[
                (
                    "~/.cursor/mcp.json",
                    _json({"mcpServers": {nazwa: {"url": adres("cursor")}}}),
                )
            ],
        ),
        klient(
            "vscode",
            "Visual Studio Code (GitHub Copilot)",
            linki=[link_vscode(nazwa, adres("vscode"))],
            wklejki=[
                (
                    polecenie,
                    "code --add-mcp '"
                    + json.dumps(
                        {"name": nazwa, "type": "http", "url": adres("vscode")},
                        separators=(",", ":"),
                    )
                    + "'",
                )
            ],
            uwagi=[
                _("Narzędzia serwera są dostępne w trybie agenta GitHub Copilot."),
            ],
        ),
        klient(
            "gemini-cli",
            "Gemini CLI",
            wklejki=[
                (
                    polecenie,
                    "gemini mcp add --transport http --scope user "
                    f"{nazwa} {adres('gemini-cli')}",
                )
            ],
            uwagi=(
                [
                    _(
                        "Po dodaniu uruchom w sesji Gemini CLI polecenie "
                        "/mcp auth %(nazwa)s, żeby się zalogować."
                    )
                    % {"nazwa": nazwa}
                ]
                if adres("gemini-cli") == adres_z_logowaniem
                else []
            ),
        ),
        klient(
            "windsurf",
            "Windsurf",
            wklejki=[
                (
                    "~/.codeium/windsurf/mcp_config.json",
                    _json({"mcpServers": {nazwa: {"serverUrl": adres("windsurf")}}}),
                )
            ],
        ),
        klient(
            "zed",
            "Zed",
            kroki=[
                _(
                    "Otwórz Settings → AI → MCP Servers i kliknij Add Remote "
                    "Server — albo dopisz wpis do settings.json."
                ),
            ],
            wklejki=[
                (
                    "settings.json",
                    _json({"context_servers": {nazwa: {"url": adres("zed")}}}),
                )
            ],
        ),
        klient(
            "lm-studio",
            "LM Studio",
            linki=[link_lmstudio(nazwa, adres("lm-studio"))],
            wklejki=[
                (
                    "mcp.json",
                    _json({"mcpServers": {nazwa: {"url": adres("lm-studio")}}}),
                )
            ],
            uwagi=[_("Wymaga LM Studio w wersji 0.3.17 lub nowszej.")],
        ),
        klient(
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
            wklejki=[(adres_serwera, adres("le-chat"))],
        ),
        klient(
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
            wklejki=[(adres_serwera, adres("copilot-studio"))],
            uwagi=[
                _(
                    "W Microsoft 365 Copilot własny serwer MCP rejestruje "
                    "administrator."
                ),
            ],
        ),
    ]
