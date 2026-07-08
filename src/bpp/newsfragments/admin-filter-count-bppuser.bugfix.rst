Liczniki filtrów w adminie: naprawiono ``NoReverseMatch`` (połykany wyjątek,
szum w logach/Rollbarze) przy filtrowaniu changelistów adminów bez endpointu
``_filter_count`` (np. użytkownicy). Licznik jest teraz liczony wyłącznie tam,
gdzie admin faktycznie wystawia ten endpoint.
