Naprawiono wyciek scommitowanych danych między testami importu pracowników.
Autouse fixture zerował marker działającej pętli zdarzeń na czas testu
i przywracał go po — a ponieważ Django wybiera magazyn połączeń po tym
markerze (``asgiref.local.Local(thread_critical=True)``), zapisy testu
trafiały na inne połączenie, poza jego transakcją, i commitowały się mimo
``django_db``.
