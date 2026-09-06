"""Stan endpointu MCP dla monitoringu.

Grupa zadań menedżera sesji MCP (``StartMcp``) może zostać zatruta wyjątkiem
dziecka — proces wtedy żyje, ale każde ``/mcp`` zwraca błąd aż do recyklingu
workera. Healthcheck musi więc odróżniać „proces działa" od „endpoint MCP
działa" (spec §10.3): drugie jest ostrzejszym warunkiem od pierwszego.
"""

from __future__ import annotations


def stan_mcp() -> dict:
    """Zwróć stan startu serwera MCP z ``StartMcp`` wystawionego przez ASGI.

    Import wewnątrz funkcji (nie na szczycie modułu): ``django_bpp.asgi``
    buduje aplikację MCP przy imporcie (``build_application()``), więc
    importowanie go na szczycie tego modułu ściągnęłoby ten koszt do każdego
    miejsca, które tylko chce zaimportować ``stan_mcp`` (np. testy).
    """
    from django_bpp.asgi import _mcp_start

    return {
        "wystartowany": _mcp_start.wystartowany,
        "zywy": _mcp_start.zywy,
    }
