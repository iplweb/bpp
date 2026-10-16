Zapytania w języku DjangoQL — w module Redagowanie, na stronie „Szukaj
zapytaniem" oraz w REST API (``/api/v1/zapytanie/``) — domyślnie NIE pokazują
już rekordów skasowanych (kosz). Żeby zajrzeć do kosza, wystarczy wymienić w
zapytaniu pole ``deleted_at`` na wybranej relacji: warunek
``autorzy_set.deleted_at != None`` pokazuje wyłącznie skasowane pozycje,
a ``autorzy_set.deleted_at = None`` jest tym samym, co zachowanie domyślne.
