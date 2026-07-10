API ``/api/v1/`` zyskało wyszukiwanie: nowy endpoint ``GET /api/v1/szukaj/``
(rankowane wyszukiwanie pełnotekstowe po wszystkich typach publikacji, parametry
``q``, ``rok_od``, ``rok_do``, paginacja LimitOffset), filtr ``autor/?nazwisko=``
(dopasowanie częściowe, bez rozróżniania wielkości liter) oraz filtr ``?autor=``
na endpointach ``wydawnictwo_ciagle_autor`` / ``wydawnictwo_zwarte_autor``
(pełny harvest prac autora). Endpoint ``/szukaj/`` respektuje ukrywanie rekordów
(``nie_eksportuj_przez_api``, ukryte statusy korekty) oraz zawężenie
multi-uczelnia.
