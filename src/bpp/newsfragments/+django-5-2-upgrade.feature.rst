Migracja do Django 5.2 LTS. System korzysta teraz z Django w wersji
5.2.x zamiast 4.2.x; 4.2 LTS wchodzi w fazę EOL w kwietniu 2026 i
traci wsparcie bezpieczeństwa.

W ramach migracji zaktualizowano pakiety zależne do wersji
kompatybilnych z Django 5.2: ``django-crispy-forms``, ``django-mptt``,
``django-tables2``, ``django-taggit``, ``django-filter``,
``django-import-export`` (z 3.x na 4.x), ``django-grappelli`` (z 3.x
na 4.x), ``django-fsm``, ``django-reversion``, oraz ``Unidecode``.

Porzucone ``django-htmlmin`` (brak wydań od 2019 r.) zastąpione przez
utrzymywane ``django-minify-html`` — minyfikator HTML oparty o
rust-owy ``minify-html``. Middleware jest aktywne tylko w środowisku
produkcyjnym, tak jak dotychczas.

Nie wymaga interwencji administratora — wszystkie zmiany są
transparentne na poziomie interfejsu użytkownika i panelu admina.
