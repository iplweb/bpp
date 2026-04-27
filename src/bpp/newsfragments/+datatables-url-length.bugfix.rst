Naprawiono blokowanie zapytań AJAX widgetów DataTables przez
``MaliciousRequestBlockingMiddleware``. Limit długości pełnego URL-a
(``MAX_FULL_PATH_LENGTH``) został podniesiony z 2048 na 8192 — DataTables
przy ~10 kolumnach generuje query string z percent-encoded metadanymi
kolumn (``columns%5B0%5D%5Bdata%5D=…``) przekraczający 2 KB, ale dobrze
mieszczący się w 8 KB (zgodnie z domyślnym ``large_client_header_buffers``
nginxa i ``LimitRequestLine`` Apacha). Eksponencjalnie rosnące łańcuchy
``?next=`` produkowane przez bot-skannery nadal są łapane — albo przez
nowy próg, albo przez detektor zagnieżdżonego ``?next=``.
