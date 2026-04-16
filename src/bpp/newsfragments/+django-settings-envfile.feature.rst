Zmienna ``DJANGO_SETTINGS_MODULE`` została przeniesiona z sekcji
``environment:`` kontenerów (``appserver``, ``celerybeat``,
``workerserver-*``, ``denorm-queue``) do plików ``.env`` / ``.env.docker``
/ ``.env.example``. Devowy docker-compose konsekwentnie używa ustawień
``django_bpp.settings.local``; serwis ``authserver`` pozostaje bez
zmian (korzysta z własnego modułu ``django_bpp.settings.auth_server``).
