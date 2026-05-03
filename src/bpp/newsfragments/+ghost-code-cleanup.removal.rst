Usunięto pozostałości po niezainstalowanej integracji
Sentry: moduł ``django_bpp.sentry_support``, jego test,
endpoint ``/sentry_test/`` oraz sekcja ``SENTRYSDK_*``
w ``.env.example``. Projekt używa Rollbara — żadne
ustawienie Sentry nie było aktywne, a artefakty wprowadzały
w błąd. Endpointy ``/test_403/``, ``/test_500/``
i ``/test_exception/`` (do podglądu stron błędów i
weryfikacji integracji Rollbara) pozostają.

Z ``package.json`` usunięto pakiet ``font-awesome 4.1.0``
(nie był importowany przez bundle ani template'y; biblioteka
po EOL z dostępnymi CVE). Aktywnie używany ``jqueryui 1.11.1``
zostaje — wymiana wymaga osobnej, większej zmiany.

Z ``bpp/tasks.py`` usunięto martwą funkcję ``my_limit()``
i moduł-globalny słownik ``task_limits`` — funkcja nie była
nigdzie wywoływana, a per-procesowy słownik nie miał szans
działać poprawnie z wieloma workerami.
