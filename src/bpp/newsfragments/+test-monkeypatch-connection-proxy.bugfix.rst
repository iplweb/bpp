``test_health_check_returns_503_when_db_down`` zatruwał blocker
``pytest-django`` dla całego workera xdist (``monkeypatch.setattr`` na
``ConnectionProxy`` wstrzykiwał bound ``_blocking_wrapper`` do
``connections[default].__dict__``, co nadpisywało class-level patch
i czyniło ``django_db_blocker.unblock()`` bezskutecznym). Multiseek
testy padały deterministycznie 50 errors w ``setup_databases``.
Patch zmieniony na ``health._check_db`` (symetrycznie do testu
redis-down). Dodatkowo middleware ``test_logging_*`` w
``test_page_validation.py`` zyskały autouse fixture wpinający
``caplog.handler`` bezpośrednio do loggera ``django.request`` —
po zmianie ``propagate=False`` z commita audytu caplog nie widział
WARNING-ów o zablokowanych żądaniach.
