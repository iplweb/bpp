Zmniejszono rozmiar obrazów Docker o ~25% (z ~1.67 GB do ~1.25 GB
rozpakowanego ``iplweb/bpp_appserver``). Zmiany w ``docker/bpp_base``:

- ``collectstatic`` uruchamiany w builder stage — ``node_modules``
  (~327 MB) nie trafia już do runtime, shipowany jest tylko pre-
  populowany ``/app/staticroot``.
- ``uv`` usunięty ze stage ``runtime`` — entrypointy używają
  ``python``/``celery``/``uvicorn``/``gunicorn`` wprost z ``.venv/bin``.
- Poprawiono błąd w zmiennej ``PATH`` (wskazywała ``/.venv/bin``
  zamiast ``/app/.venv/bin``) — działało to tylko dzięki ``uv run``.
- ``pygad`` instalowany bez ``matplotlib`` (biblioteka używana wyłącznie
  dla nieużywanych funkcji plotowania zbieżności algorytmu genetycznego).
- ``uv sync`` ograniczony do realnych extras produkcyjnych
  (``--extra ldap --extra office365``) zamiast ``--all-extras``;
  ``testcontainers`` oraz pakiety z grupy dev nie trafiają już do
  obrazu.
- ``gunicorn`` oraz ``watchdog`` przeniesione do głównych zależności
  w ``pyproject.toml`` — wcześniej były doinstalowywane runtime'owo
  przez ``uv pip install``.
- Katalogi ``tests`` na poziomie aplikacji oraz ``src/integration_tests``
  nie są już kopiowane do obrazów produkcyjnych.
