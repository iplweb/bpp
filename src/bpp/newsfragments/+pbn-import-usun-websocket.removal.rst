Import PBN: usunięto martwą warstwę WebSocket/Channels (konsumenci,
routing, helpery powiadomień). Niezgodność koperty komunikatów sprawiała,
że żadna wiadomość WS nie docierała do przeglądarki — cały podgląd
postępu na żywo i tak realizuje odpytywanie HTMX, które pozostaje bez
zmian. Mniej kodu i jedna zależność ASGI mniej, bez zmiany zachowania.
