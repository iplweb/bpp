Tytuły obcojęzyczne publikacji są teraz oznaczane atrybutem ``lang``
(kryterium WCAG 2.2 AA 3.1.2) — na stronach szczegółów, listach i w wynikach
wyszukiwania. Czytnik ekranu odczyta angielski tytuł angielską fonetyką
zamiast polskiej. Wymaga wypełnionego pola „Kod języka wg BCP 47" w słowniku
języków; opisy bibliograficzne złapią znacznik po najbliższym nocnym
przeliczeniu. Jeśli administrator ma w bazie własną wersję szablonu
``opis_bibliograficzny.html`` (zapisaną kiedyś w panelu „Szablony stron"),
znacznik go nie obejmie — trzeba dopisać filtr ``oznacz_jezyk`` ręcznie albo
usunąć wiersz komendą ``manage.py drop_dbtemplate opis_bibliograficzny.html``,
żeby wrócić do wersji z repozytorium.
