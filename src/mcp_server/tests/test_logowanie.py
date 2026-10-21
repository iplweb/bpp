"""Ślad audytowy żądań /mcp (spec §7.5) — i to, czego w nim BYĆ NIE MOŻE.

Żądania na ``/mcp`` nie trafiają ani do access-logu nginksa (wewnętrzne
wywołania go omijają), ani uvicorna w formie użytecznej do audytu. Publiczny,
nieuwierzytelniony endpoint na produkcyjnej domenie uczelni nie zostawiał
przed tą poprawką ŻADNEGO śladu — nie było jak zbadać nadużycia ani zmierzyć
obciążenia.

Spec wymaga wprost: „Logujemy je w KontekstMcp (ścieżka, kod, czas, obecność
bearera — **nigdy token**)”.
"""

import logging

import pytest

from mcp_server.routing import RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope

pytestmark = pytest.mark.django_db(transaction=True)

TOKEN = "SEKRETNY-TOKEN-KTORY-NIE-MOZE-TRAFIC-DO-LOGU"


class _AtrapaLifespanu:
    def __init__(self):
        self.router = self

    def lifespan_context(self, _app):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            yield

        return _ctx()


async def _mcp(scope, receive, send):
    await send({"type": "http.response.start", "status": 207, "headers": []})
    await send({"type": "http.response.body", "body": b"MCP"})


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _token_w_bazie(raw):
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from model_bakery import baker
    from oauth2_provider.models import get_access_token_model, get_application_model

    user = baker.make(get_user_model(), is_active=True)
    app = get_application_model().objects.create(
        name="test-log",
        client_type="public",
        authorization_grant_type="authorization-code",
    )
    return get_access_token_model().objects.create(
        user=user,
        application=app,
        token=raw,
        scope="read",
        expires=timezone.now() + timedelta(seconds=3600),
    )


def _wywolaj(naglowki=None):
    router = RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))
    return uruchom(
        lambda: wywolaj(router, zbuduj_scope("/mcp", naglowki=naglowki or {}))
    )


def test_log_ma_sciezke_kod_czas_host_i_brak_bearera(caplog, uczelnia):
    with caplog.at_level(logging.INFO, logger="mcp_server.routing"):
        status, _, _ = _wywolaj()
    assert status == 207
    (rekord,) = [r for r in caplog.records if r.name == "mcp_server.routing"]
    wiadomosc = rekord.getMessage()
    assert "/mcp" in wiadomosc
    assert "status=207" in wiadomosc, "kod odpowiedzi musi być w logu"
    assert "host=bpp.example.test" in wiadomosc
    assert "bearer=nie" in wiadomosc
    assert "czas=" in wiadomosc


def test_log_odnotowuje_obecnosc_bearera_ale_nie_jego_wartosc(caplog, uczelnia):
    """Sedno wymogu: OBECNOŚĆ, nigdy wartość. Token w logu byłby
    poświadczeniem leżącym w pliku, który wędruje do agregatora i backupów."""
    _token_w_bazie(TOKEN)
    with caplog.at_level(logging.INFO, logger="mcp_server.routing"):
        _wywolaj({"authorization": f"Bearer {TOKEN}"})

    rekordy = [r for r in caplog.records if r.name == "mcp_server.routing"]
    assert rekordy, "żądanie z bearerem musi zostawić ślad"
    assert "bearer=tak" in rekordy[0].getMessage()

    # Cały strumień logów, nie tylko nasz rekord — token nie może wyciec
    # ŻADNĄ drogą (argumenty formatowania, wyjątki, warstwy niżej).
    caly_log = "\n".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in caly_log
    assert TOKEN not in "".join(str(a) for r in caplog.records for a in (r.args or ()))


def test_log_powstaje_takze_gdy_zadanie_zostalo_odrzucone(caplog):
    """Odrzucone żądania są tym, co audyt interesuje NAJBARDZIEJ — log leci
    z ``finally``, więc powstaje niezależnie od tego, którą gałęzią wyszliśmy.
    Bez uczelni w bazie bramka odrzuca 421-ką."""
    with caplog.at_level(logging.INFO, logger="mcp_server.routing"):
        status, _, _ = _wywolaj()
    assert status == 421
    (rekord,) = [
        r
        for r in caplog.records
        if r.name == "mcp_server.routing" and r.levelno == logging.INFO
    ]
    assert "status=421" in rekord.getMessage()
