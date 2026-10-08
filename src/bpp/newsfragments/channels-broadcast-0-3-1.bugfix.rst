Powiadomienia WebSocket wysyłane z kontekstu asynchronicznego (ASGI) nie
przewracają się już o błąd ``asyncio.run() cannot be called from a running
event loop``. Przyczyna była w pakiecie ``django-channels-broadcast``, który
łatał asyncio globalnie dla całego procesu; poprawka weszła w jego wersji
0.3.1 i BPP jej teraz wymaga.
