Import list ministerialnych korzysta teraz z pakietu ``django-liveops``
(podgląd postępu na żywo przez WebSocket + HTMX) zamiast wewnętrznej
aplikacji ``long_running``. Dodano cienką warstwę ``bpp_liveops``
(``BppLiveOperation`` + centralne, generyczne widoki live/cancel/restart),
która pozostaje do wykorzystania przy migracji kolejnych importów.
