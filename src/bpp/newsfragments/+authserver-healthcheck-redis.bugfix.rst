Naprawiono healthcheck lekkiego ``authserver``-a, który zwracał
``503 Service Unavailable`` przez ``AttributeError`` na nieistniejącym
``settings.CELERY_BROKER_URL``. Sonda Redis jest teraz pomijana, gdy
ustawienia nie konfigurują brokera Celery — ``authserver`` nie używa
kolejki zadań, więc jego stan zdrowia nie zależy od Redis-a. Sonda
PostgreSQL działa bez zmian.
