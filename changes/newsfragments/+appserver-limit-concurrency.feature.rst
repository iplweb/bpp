Appserver ma limit równoczesnych połączeń na proces (``GUNICORN_LIMIT_CONCURRENCY``,
domyślnie 80, ``0`` = bez limitu). Ponad limit od razu odpowiada 503, zamiast
otwierać kolejne połączenia z PostgreSQL — przy floodzie z tysięcy adresów IP baza
nie kończy już na ``too many clients`` dla wszystkich, łącznie z Celery.
