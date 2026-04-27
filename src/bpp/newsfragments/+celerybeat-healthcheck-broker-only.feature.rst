Uproszczono healthcheck kontenera ``celerybeat`` — sprawdza on teraz
wyłącznie dostępność brokera (RabbitMQ) przez świeże połączenie AMQP,
bez wcześniejszego dwustopniowego badania pidfile + brokera.

Sprawdzenie żywotności procesu beata przez ``/celerybeat.pid`` było
redundantne, ponieważ ``celery beat`` jest procesem PID 1 kontenera —
gdy padnie, kontener wychodzi i healthcheck nie jest wtedy nawet
uruchamiany. Pozostawienie wyłącznie sondy brokera daje to, czego
healthcheck nie wie z samego faktu, że kontener jeszcze biegnie.

Dodatkowo usunięto pośredni skrypt ``docker/beatserver/healthcheck.sh``
— ``HEALTHCHECK`` w ``docker/beatserver/Dockerfile`` woła teraz
bezpośrednio ``python /app/healthcheck_broker.py``.
