Eksport schematu DjangoQL dla LLM obejmuje teraz trzy kanoniczne korzenie
(``bpp.Rekord``, ``bpp.Autor``, ``bpp.Autorzy``) — pełny round-trip dla
endpointów ``/api/v1/zapytanie/{rekord,autor,autorzy}/``. Komenda
``opisz_schemat_djangoql_dla_llm`` zyskała tryb ``--wszystkie-korzenie``
(generuje wszystkie trzy naraz) oraz wyprowadzanie ścieżki wyjścia z ``--model``.
Wszystkie korzenie używają tego samego bezpiecznego ``RekordLLMSchema``
(blocklist PII + brak nazw instytucji + wartości tylko bezpiecznych słowników).
