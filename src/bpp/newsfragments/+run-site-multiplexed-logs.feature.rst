Polecenie ``manage.py run_site`` strumieniuje teraz logi
runservera, celery i PostgreSQL równocześnie do jednego
terminala z kolorowymi prefiksami (``web``, ``celery``, ``pg``)
— jak ``docker compose up``. Linie z różnych procesów są
serializowane przez wątkowy multiplekser, więc się nie sklejają.
Dodatkowo na lokalnym dev-stacku z ``run_site`` cookie banner
jest automatycznie ukrywany — endpoint auto-loginu ustawia
cookie ``cookielaw_accepted=1`` w odpowiedzi z przekierowaniem,
co przy zwyczajowym workflow (uruchom ``run_site`` → przeglądarka
otwiera autologin → przekierowanie na ``/``) eliminuje banner.
