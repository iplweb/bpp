Aktualizacja do Django 6.1. Minimalna wersja Pythona to teraz 3.12
(wymaganie Django 6.1). Backend cache'u wrócił z forku
``django-redis-iplweb`` na upstreamowy ``django-redis`` — nazwa modułu
w konfiguracji (``django_redis.cache.RedisCache``) się nie zmienia,
więc wdrożenia nie wymagają zmian.
