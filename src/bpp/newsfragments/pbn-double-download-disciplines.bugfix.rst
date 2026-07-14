Usunięto podwójne pobieranie słownika dyscyplin z PBN podczas integracji i
initial-setupu — ``sync_disciplines()`` samo pobiera słownik, więc dodatkowe
``download_disciplines()`` tuż przed nim tylko dublowało zapytanie do PBN.
