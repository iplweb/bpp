"""Limit równoległości appservera (``GUNICORN_LIMIT_CONCURRENCY``).

Bez limitu uvicorn przyjmuje dowolnie wiele równoległych żądań, a każde
trzyma własne połączenie z PostgreSQL. Scraper z ~7 tys. adresów IP
(publikacje.up.lublin.pl, 2026-09-27) spiętrzył je ponad ``max_connections``
i baza odpowiadała ``too many clients`` każdemu, łącznie z workerami.

Testy sprawdzają nie sam słownik z configu, tylko to, co faktycznie ląduje
w ``uvicorn.Config`` po zbudowaniu workera — ``CONFIG_KWARGS`` jest
doklejany w ``UvicornWorker.__init__``, więc literówka w nazwie klucza
przeszłaby asercję na słowniku, a limitu by nie było.
"""

import logging
import runpy
from pathlib import Path
from unittest import mock

import pytest
from gunicorn.config import Config as GunicornConfig
from uvicorn_worker import UvicornWorker

CONF_PATH = (
    Path(__file__).resolve().parents[3] / "docker" / "appserver" / "gunicorn_conf.py"
)


def _zaladuj_conf(monkeypatch, wartosc):
    if wartosc is None:
        monkeypatch.delenv("GUNICORN_LIMIT_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("GUNICORN_LIMIT_CONCURRENCY", wartosc)
    return runpy.run_path(str(CONF_PATH))


def _uvicorn_config(worker_class):
    log = mock.Mock()
    log.error_log = logging.getLogger("test.gunicorn.error")
    log.access_log = logging.getLogger("test.gunicorn.access")
    worker = worker_class(
        age=1,
        ppid=1,
        sockets=[],
        app=mock.Mock(),
        timeout=30,
        cfg=GunicornConfig(),
        log=log,
    )
    return worker.config


def test_domyslny_limit_dociera_do_uvicorna(monkeypatch):
    conf = _zaladuj_conf(monkeypatch, None)
    assert issubclass(conf["worker_class"], UvicornWorker)
    assert _uvicorn_config(conf["worker_class"]).limit_concurrency == 80


def test_limit_z_env(monkeypatch):
    conf = _zaladuj_conf(monkeypatch, "25")
    assert _uvicorn_config(conf["worker_class"]).limit_concurrency == 25


def test_pusta_wartosc_to_domyslny_limit(monkeypatch):
    conf = _zaladuj_conf(monkeypatch, "")
    assert _uvicorn_config(conf["worker_class"]).limit_concurrency == 80


def test_zero_wylacza_limit(monkeypatch):
    conf = _zaladuj_conf(monkeypatch, "0")
    assert _uvicorn_config(conf["worker_class"]).limit_concurrency is None


@pytest.mark.parametrize("smiec", ["abc", "-5", "10.5", " 7x"])
def test_bledna_wartosc_nie_kladzie_appservera(monkeypatch, capsys, smiec):
    # Literówka w .env nie może zatrzymać startu całego serwisu — wracamy do
    # domyślnego limitu i mówimy o tym głośno na stderr (logi kontenera).
    conf = _zaladuj_conf(monkeypatch, smiec)
    assert _uvicorn_config(conf["worker_class"]).limit_concurrency == 80
    assert "GUNICORN_LIMIT_CONCURRENCY" in capsys.readouterr().err


def test_pozostale_ustawienia_uvicorn_worker_zachowane(monkeypatch):
    # Podklasa ma DOKLEIĆ limit, a nie zgubić loop/http z klasy bazowej.
    conf = _zaladuj_conf(monkeypatch, None)
    kwargs = conf["worker_class"].CONFIG_KWARGS
    for klucz, wartosc in UvicornWorker.CONFIG_KWARGS.items():
        assert kwargs[klucz] == wartosc
