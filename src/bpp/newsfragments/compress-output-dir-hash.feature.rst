Statyki (JS/CSS) nie są już unieważniane w cache przeglądarki przy każdym
wydaniu. Katalog wyjściowy django-compressor przestał zawierać numer wersji
(``CACHE-{VERSION}`` → ``CACHE``); pliki i tak są nazywane hashem swojej
treści, więc ścieżka zmienia się tylko wtedy, gdy realnie zmieni się JS/CSS —
deploy bez zmian we front-endzie oszczędza użytkownikom ~305 KB gzip zbędnego
pobierania.
