"""Dane zewnętrznego żądania, przenoszone do warstwy wykonującej narzędzia.

Klient MCP żyje w lifespanie (jeden na proces), a host, protokół, IP i token
zależą od KONKRETNEGO żądania. Przenosimy je ContextVarem — MCP SDK celowo
kopiuje kontekst przez granicę zadań (transport zapisuje ``copy_context()``
nadawcy, dispatcher odtwarza go przy uruchamianiu handlera), więc wartość
ustawiona w warstwie ASGI jest widoczna w kodzie narzędzia.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


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
