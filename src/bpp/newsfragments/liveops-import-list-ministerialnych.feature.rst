Import list ministerialnych korzysta teraz z pakietu ``django-liveops``
(podgląd postępu na żywo przez WebSocket + HTMX) zamiast wewnętrznej
aplikacji ``long_running``. Routing live/cancel/restart jest generyczny
(``op_type`` = ``<app_label>.<model_name>``) i mieszka w samym pakiecie
liveops, więc konwersja kolejnych importów nie wymaga żadnej warstwy
pośredniej po stronie BPP.
