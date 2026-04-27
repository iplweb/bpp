Broker Celery przeniesiony z RabbitMQ na Redis (baza ``DB 1``,
zmienna ``DJANGO_BPP_REDIS_DB_BROKER``). Result backend (Redis ``DB 2``)
i routing tasków bez zmian — migracja jest neutralna funkcjonalnie.

Usunięte zostały:

- serwis ``rabbitmq`` z ``docker-compose.yml`` i
  ``docker-compose.test.yml``,
- zmienne ``DJANGO_BPP_RABBITMQ_*`` z konfiguracji oraz
  ``.env.docker`` / ``.env.example``,
- zależność pakietu ``amqp`` z ``pyproject.toml``,
- start kontenera RabbitMQ w plugin-ie ``testcontainers_bpp``,
- pozycja „RabbitMQ" z menu admina (DOCKER_SERVICES_MENU).

Po pull-u wymagany jest ``uv lock`` / rebuild obrazów (zniknie
biblioteka ``amqp``); istniejące deploye po przepięciu wymagają
``stop workers → up -d → start workers``. Zadania zalegające
w kolejce RabbitMQ przy migracji zostaną porzucone.

Lokalne ``docker compose up`` startuje teraz znacząco szybciej —
RabbitMQ pod emulacją amd64 na arm64 potrafił rozgrzewać się
~3 minuty, Redis w sekundę.

Dla deploymentów: zmiany w ``bpp-deploy`` (compose, init-configs,
prometheus job, nginx routing ``/rabbitmq/``) muszą zostać
wdrożone razem z tą wersją obrazu — szczegóły w ``CHANGELOG`` repo
``iplweb/bpp-deploy``.

Dodano ``CELERY_BROKER_TRANSPORT_OPTIONS`` z ``visibility_timeout``
ustawionym na 6 godzin — Redis re-deliveruje zadanie po tym
timeout-cie jeśli worker padł, więc wartość musi przekraczać
najdłuższy realny task (PBN export, import POLON).
