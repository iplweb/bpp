Context processor ``bpp.context_processors.constance_config`` używa
teraz ``constance.utils.get_values_for_keys`` zamiast
``getattr(config, key)``. Od django-constance 4.x
``Config.__getattr__`` wykrywa aktywną pętlę ``asyncio`` i zwraca
``AsyncValueProxy`` zamiast bezpośredniej wartości. Django test
client w nowszych wersjach startuje pętlę wewnętrznie, więc w
testach (i faktycznie w ASGI-runtime) szablony renderujące
``{{ WYDRUK_MARGINES_GORA|default:"2cm" }}`` emitowały
``RuntimeWarning: Synchronous access to Constance setting
'WYDRUK_MARGINES_*' inside an async loop``.
``get_values_for_keys`` idzie prosto do backendu, bez detekcji
pętli, więc działa identycznie w obu kontekstach i nie odpala
warningu.
