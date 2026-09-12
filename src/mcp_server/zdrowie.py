"""Stan endpointu MCP dla monitoringu (spec §10.3).

Grupa zadań menedżera sesji MCP (``StartMcp``) może zostać zatruta wyjątkiem
dziecka — proces wtedy żyje, ale każde ``/mcp`` zwraca błąd aż do recyklingu
workera. Monitoring musi więc odróżniać „proces działa” od „endpoint MCP
działa”: drugie jest ostrzejszym warunkiem od pierwszego.

**Dlaczego to NIE jest wpięte w ``/health/``.** Tamten endpoint jest sondą
Dockera (``docker/appserver/*``): 503 z niego restartuje cały appserver.
Awaria izolowana do MCP zabijałaby wtedy serwis, który poza ``/mcp`` działa
bez zarzutu — lekarstwo gorsze od choroby. Stąd osobny adres ``/mcp/status``,
obsługiwany przez ``RouterHttp`` (a nie przez Django), dzięki czemu odpowiada
bez uwierzytelnienia, bez bazy i bez przechodzenia przez cały stos middleware.
"""

from __future__ import annotations


def stan_startu(start) -> tuple[dict, int]:
    """Zwróć ``(treść JSON, kod HTTP)`` opisujące stan menedżera sesji MCP.

    Czysta funkcja nad ``StartMcp`` — bierze obiekt, którym dysponuje warstwa
    ASGI. Poprzednia wersja sięgała po ``django_bpp.asgi._mcp_start`` sama
    i nie była wołana z ŻADNEGO miejsca produkcyjnego; szew przez argument
    pozwala testom podstawić prawdziwy, zatruty ``StartMcp``, zamiast atrapy
    z dwoma atrybutami, która przeszłaby przy dowolnej implementacji.

    ``zywy`` (a nie ``wystartowany``) rozstrzyga o kodzie: to ono odpowiada
    na pytanie „czy POST /mcp da teraz odpowiedź”. ``wystartowany`` zostaje
    w treści, bo odróżnia „jeszcze nie wstał” od „wstał i padł” — czyli mówi,
    czy warto czekać, czy trzeba restartować workera.
    """
    zywy = start.zywy
    tresc = {
        "status": "ok" if zywy else "error",
        "wystartowany": start.wystartowany,
        "zywy": zywy,
    }
    return tresc, (200 if zywy else 503)
