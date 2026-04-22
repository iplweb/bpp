Zaktualizowano zależności bezpieczeństwa wskazane przez Dependabot:
``werkzeug`` ``3.1.3`` → ``3.1.8`` (naprawa ``safe_join()`` dla
nazw urządzeń specjalnych Windows; transient dep przez
``pytest-httpserver``) oraz ``sqlparse`` ``0.5.3`` → ``0.5.5``
(DoS przy formatowaniu list krotek; transient dep przez Django).
