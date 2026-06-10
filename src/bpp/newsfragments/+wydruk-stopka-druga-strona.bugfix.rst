Wydruki (m.in. raporty z multiseek) nie zajmują już niepotrzebnie
dodatkowej, prawie pustej strony. Stopka „Dokument wygenerowano przy
pomocy systemu…” była spychana na kolejną stronę, ponieważ kontenery
treści miały na ekranie ustawione ``min-height: 100vh`` (przyklejenie
stopki do dołu okna). W druku ``100vh`` oznacza całą wysokość kartki,
więc treść była rozciągana na pełną stronę. Reguły te są teraz
neutralizowane w ``@media print``.
