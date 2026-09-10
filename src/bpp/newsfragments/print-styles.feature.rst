Uporządkowane style wydruku (``@media print``) dla serwisu publicznego
i panelu administracyjnego: znika nawigacja, stopka, banery i widgety,
tło jest białe zamiast szarego, a skala typografii została sprowadzona do
rozmiarów dokumentu (tekst 10,5 pt, nagłówki 11–16 pt) zamiast ekranowych
``rem``. Naprawione też: martwa klasa ``hide-on-print`` (nie miała
definicji w CSS, więc przycisk zgłoszeń i banery serwera testowego mimo
wszystko się drukowały), ignorowane ustawienia marginesów strony
z django-constance oraz pusta pierwsza strona wydruków z admina.
