Tytuły publikacji i opisy bibliograficzne są sanityzowane wąską allowlistą
(kursywa, indeksy dolne/górne, pogrubienie) — u źródła przy zapisie oraz przy
renderowaniu (``|safe_tytul``) — co zamyka trwały XSS z tytułów pochodzących
z importu i anonimowych zgłoszeń. Przy okazji pseudo-znaczniki liter greckich
(``<beta>``, ``<Delta>``) są zamieniane na właściwe znaki Unicode zamiast być
usuwane. Nowa komenda ``sanityzuj_tytuly`` czyści istniejące dane.
