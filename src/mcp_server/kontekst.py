"""Dane zewnętrznego żądania, przenoszone do warstwy wykonującej narzędzia.

Klient MCP żyje w lifespanie (jeden na proces), a host, protokół, IP i token
zależą od KONKRETNEGO żądania. Przenosimy je ContextVarem — MCP SDK celowo
kopiuje kontekst przez granicę zadań (transport zapisuje ``copy_context()``
nadawcy, dispatcher odtwarza go przy uruchamianiu handlera), więc wartość
ustawiona w warstwie ASGI jest widoczna w kodzie narzędzia.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass

from django.conf import settings
from django.http.request import split_domain_port


@dataclass(frozen=True)
class DaneZadania:
    """Wszystko, czego wewnętrzne żądanie nie ma skąd wziąć samo."""

    host: str
    scheme: str
    ip: str
    bearer: str | None
    deadline: float | None  # monotoniczny znacznik końca budżetu


dane_zadania: ContextVar[DaneZadania | None] = ContextVar(
    "mcp_dane_zadania", default=None
)


def biezace() -> DaneZadania:
    """Zwróć dane bieżącego żądania albo rzuć — NIGDY nie zgaduj.

    Fallback na wartości domyślne oznaczałby ciche żądanie z nieznanego hosta,
    czyli obejście bramki API i wyciek między uczelniami (spec §7.2).
    """
    dane = dane_zadania.get()
    if dane is None:
        raise RuntimeError(
            "Brak kontekstu żądania MCP — warstwa KontekstMcp nie została "
            "uruchomiona albo ContextVar został zresetowany za wcześnie."
        )
    return dane


def domena_hosta(host: str) -> str:
    """Zwróć część domenową nagłówka ``Host`` — albo ``""``, gdy jest niepoprawny.

    JEDNO źródło prawdy o tym, czym jest poprawny ``Host`` na ścieżce ``/mcp``,
    używane w DWÓCH miejscach: przez bramkę w ``routing.RouterHttp`` (odrzuca
    niepoprawny nagłówek 421-ką) i przez ``klient.BppClientInProcess`` (porównuje
    host URL-a wychodzącego z hostem żądania). Rozjazd między tymi dwoma
    miejscami już raz kosztował — patrz komentarze w obu.

    Używamy ``django.http.request.split_domain_port``, czyli DOKŁADNIE tej samej
    funkcji (i tego samego ``host_validation_re`` z numerycznym portem), którą
    Django stosuje w ``HttpRequest.get_host()``. Dlaczego nie własne
    ``host.split(":")[0]``:

    * ``TransportSecuritySettings`` SDK dopasowuje wzorzec ``host:*`` przez
      ``host.startswith(base_host + ":")`` (``mcp/server/transport_security.py``)
      — portu NIE waliduje, więc ``uczelnia.example:abc``, ``:1:2`` czy ``:0x1F``
      przechodzą jego kontrolę;
    * ``uczelnia._rozstrzygalny`` obcinał port przez ``split(":")[0]``, więc
      dostawał prawdziwy ``Site`` i przepuszczał żądanie dalej;
    * ``klient.BppClientInProcess`` budował ``Config(base_url=f"{scheme}://
      {host}")``, a ``httpx.URL`` na niepoprawnym porcie rzucał ``ValueError``
      — czyli wyjątek, który NIE jest ani ``httpx.HTTPError`` (więc
      ``BppClient._request`` go nie łapie), ani ``BppError`` (więc wrapper
      ``aplikacja._z_raportowaniem`` robił ``rollbar.report_exc_info()``).

    Razem dawało to anonimowy, nielimitowany kanał do Rollbara: jedno żądanie
    z ``Host: <uczelnia>:abc`` = jedno zgłoszenie, a ``curl`` w pętli wyczerpywał
    kwotę i topił realne alerty. Django-owe ``get_host()`` (z tym samym regexem)
    NIE jest na tej ścieżce, bo żądanie nie przechodzi przez ``HttpRequest``.
    """
    domena, _port = split_domain_port(host)
    return domena


def _naglowek_schematu() -> tuple[str, str]:
    """Nazwa nagłówka niosącego prawdziwy schemat i wartość znacząca „https”.

    Czytamy z ``SECURE_PROXY_SSL_HEADER``, a NIE z zaszytego na sztywno
    ``X-Forwarded-Proto``, bo w tym repozytorium te dwie rzeczy to nie to samo:
    ``settings/base.py`` deklaruje ``HTTP_X_FORWARDED_PROTOCOL``, a
    ``settings/production.py`` — ``HTTP_X_FORWARDED_PROTO``. Zaszycie jednej
    z tych nazw sprawiłoby, że warstwa MCP rozjeżdża się z Django dokładnie
    w jednym z dwóch środowisk — po cichu, bo objawem jest tylko zły schemat
    w składanych adresach (PRM w ``WWW-Authenticate``, ``base_url`` klienta).

    Klucz ASGI jest małymi literami i z myślnikami, więc tłumaczymy nazwę
    z konwencji ``request.META`` (``HTTP_X_FORWARDED_PROTO``) na nagłówkową
    (``x-forwarded-proto``).
    """
    ustawienie = getattr(settings, "SECURE_PROXY_SSL_HEADER", None)
    if not ustawienie:
        # Django bez tego ustawienia w ogóle nie ufa proxy; my też nie —
        # zostaje schemat z gniazda, więc nazwa nagłówka nie ma znaczenia.
        return "", "https"
    meta, wartosc_https = ustawienie
    nazwa = meta[len("HTTP_") :] if meta.startswith("HTTP_") else meta
    return nazwa.replace("_", "-").lower(), wartosc_https


def schemat_zadania(naglowki: Mapping[str, str], domyslny: str = "http") -> str:
    """Rozstrzygnij ``http``/``https`` dla żądania z podanymi nagłówkami.

    nginx→uvicorn jest plaintext, więc ``scope["scheme"]`` mówi ``http`` nawet
    dla ruchu, który do nginksa przyszedł po HTTPS (spec §7.6). Gunicorn nie
    ustawia ``forwarded_allow_ips``, więc uvicorn nagłówkom proxy NIE ufa i sam
    schematu nie poprawi — musimy przeczytać nagłówek ręcznie.
    """
    nazwa, wartosc_https = _naglowek_schematu()
    if nazwa and naglowki.get(nazwa) == wartosc_https:
        return "https"
    return "https" if domyslny in ("https", "wss") else "http"
