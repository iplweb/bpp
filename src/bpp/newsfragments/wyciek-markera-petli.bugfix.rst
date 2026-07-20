Naprawiono wyciek scommitowanych danych między testami importu pracowników.
Autouse fixture zdejmował na czas testu wskaźnik bieżącej pętli zdarzeń
i przywracał go po — a ponieważ Django wybiera magazyn połączeń właśnie po
tym wskaźniku (``asgiref.local.Local(thread_critical=True)``), zapisy testu
trafiały na inne połączenie, poza jego transakcją, i commitowały się mimo
``django_db``. W testach liveops raportuje teraz przez ``MockProgress``,
więc ścieżka ASGI (i cały problem) w ogóle się nie uruchamia.
