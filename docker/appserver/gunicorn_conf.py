"""Gunicorn config dla ASGI appservera BPP (UvicornWorker).

Cel: ograniczyć nieograniczony wzrost RSS pojedynczego, nigdy-nierecyklowanego
procesu uvicorn. uvicorn uruchamiany samodzielnie nie ma odpowiednika
``--max-requests``, więc wolne wycieki i fragmentacja glibc malloc kumulują się
przez cały czas życia procesu (obserwowane ~1.5 GB RSS). gunicorn jako lekki
master z workerem uvicorn recykluje workera po N żądaniach, oddając pamięć do
OS — RSS dostaje pułap zamiast rosnąć monotonicznie.

Mechanika recyklingu (max_requests) — uczciwie, bez upiększeń:
- worker obsługuje swoje OSTATNIE żądanie, potem proces wychodzi; master od
  razu odradza nowego. To NIE jest blue-green „nowy wstaje zanim stary padnie".
- Socket nasłuchowy trzyma master i współdzieli z workerami, więc przychodzące
  połączenia HTTP czekają w backlogu (nie ma odrzuconych) — co najwyżej krótki
  skok latencji w oknie restartu.
- ⚠️ AKTYWNE WEBSOCKETY na recyklowanym workerze SĄ ZRYWANE. Appserver serwuje
  /asgi/notifications/ (channels) z tego samego ASGI-app, więc każdy recykling
  rozłącza podłączonych klientów (front auto-reconnectuje). Przy 1 workerze
  recykluje się ~co max_requests żądań HTTP — jeśli reconnecty są uciążliwe,
  podnieś GUNICORN_MAX_REQUESTS (rzadszy recykling) albo daj 2+ workery
  (rozłączani tylko klienci akurat recyklowanego workera).

Dev (ENABLE_AUTORELOAD_ON_CODE_CHANGE=1) NIE używa tego configu — tam entrypoint
zostaje na ``uvicorn --reload``. Ten config dotyczy tylko gałęzi produkcyjnej.
"""

import logging
import os

# Liczba workerów. Domyślnie 1 — zachowuje dotychczasowe single-process
# zachowanie uvicorna (mniejsze zużycie RAM). Override przez WEB_CONCURRENCY.
# Master gunicorna jest lekki i recykluje każdego workera niezależnie.
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
# Pakiet ``uvicorn-worker`` (osobny od uvicorn): oficjalna kontynuacja dawnego
# ``uvicorn.workers.UvicornWorker`` (deprecated i usuwany z samego uvicorn).
worker_class = "uvicorn_worker.UvicornWorker"
bind = "0.0.0.0:8000"

# Recykling: po ~max_requests (+/- jitter) żądaniach gunicorn restartuje workera,
# oddając pamięć do OS. jitter rozrzuca restarty, by przy >1 workerze nie padały
# wszystkie naraz. Override przez GUNICORN_MAX_REQUESTS / *_JITTER. Patrz uwaga
# o WebSocketach w docstringu — wyższy max_requests = rzadszy recykling = mniej
# rozłączeń WS, ale wolniejsze oddawanie pamięci.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "200"))

# Dla async-workera (UvicornWorker) ``timeout`` jest heartbeatem workera do
# mastera, NIE limitem czasu pojedynczego żądania — pętla zdarzeń pinguje
# mastera niezależnie od długości żądania. Ustawiamy hojnie pod długie
# raporty/PDF/xlsx. graceful_timeout = czas na dokończenie żądań przy recyklingu.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))


class HealthCheckFilter(logging.Filter):
    """Wytnij /health/ i /metrics z access logu — Docker healthcheck odpytuje
    /health/ co 30 s, co inaczej zalewałoby logi (parytet z
    uvicorn_log_config.json używanym w gałęzi dev)."""

    def filter(self, record):
        msg = record.getMessage()
        return "/health/" not in msg and "/metrics" not in msg


logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"health_check": {"()": HealthCheckFilter}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": ["health_check"],
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "gunicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.error": {
            "handlers": ["error_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
