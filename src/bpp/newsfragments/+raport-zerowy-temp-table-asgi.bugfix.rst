Naprawiono losowe błędy „relacja raport_slotow_raportzerowyentry
nie istnieje" przy oglądaniu raportu slotów — autorzy zerowi.
Wyniki raportu odczytywane są z tymczasowej (sesyjnej) tabeli
PostgreSQL, a odpowiedź renderowana była leniwie — pod serwerem
ASGI równoległy request (np. websocket powiadomień otwierany przez
przeglądarkę) mógł w międzyczasie zamknąć połączenie z bazą, przez
co tabela tymczasowa znikała przed odczytem. Strona raportu
renderuje się teraz w całości w obrębie tego samego połączenia.

Dodatkowo przezroczysty reconnect do bazy danych (silnik
``django_bpp.db_connclosed_fix``) loguje ostrzeżenie zamiast
działać po cichu — utrata stanu sesji PostgreSQL (tabele
tymczasowe, advisory locks) jest teraz widoczna w logach.
