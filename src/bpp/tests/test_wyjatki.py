"""Testy helpera :func:`bpp.util.zaloguj_polkniety_wyjatek`."""

import logging
from unittest import mock

from bpp.util import zaloguj_polkniety_wyjatek


def test_loguje_pelny_traceback(caplog):
    caplog.set_level(logging.ERROR)
    try:
        raise ValueError("boom")
    except ValueError:
        zaloguj_polkniety_wyjatek("Coś padło przy X", do_monitoringu=False)

    assert "Coś padło przy X" in caplog.text
    # logger.exception -> traceback z oryginalnym wyjątkiem
    assert "ValueError" in caplog.text
    assert "boom" in caplog.text


def test_uzywa_przekazanego_loggera():
    logger = mock.Mock()
    try:
        raise KeyError("k")
    except KeyError:
        zaloguj_polkniety_wyjatek("opis", logger=logger, do_monitoringu=False)

    logger.exception.assert_called_once_with("opis")


def test_zglasza_do_monitoringu_gdy_wlaczony():
    with mock.patch("bpp.util.wyjatki.capture_exception") as zglos:
        try:
            raise RuntimeError("x")
        except RuntimeError:
            zaloguj_polkniety_wyjatek("opis", do_monitoringu=True)
        zglos.assert_called_once()
        exc_info = zglos.call_args.args[0]
        assert isinstance(exc_info[1], RuntimeError)


def test_nie_zglasza_do_monitoringu_gdy_wylaczony():
    with mock.patch("bpp.util.wyjatki.capture_exception") as zglos:
        try:
            raise RuntimeError("x")
        except RuntimeError:
            zaloguj_polkniety_wyjatek("opis", do_monitoringu=False)
        zglos.assert_not_called()


def test_blad_rollbara_nie_wybucha(caplog, monkeypatch):
    """Awaria wysyłki do Rollbara nie może wysadzić kodu wołającego."""
    import rollbar

    monkeypatch.setitem(rollbar.SETTINGS, "access_token", "atrapa")
    with mock.patch(
        "bpp.zglaszanie_bledow.rollbar.report_exc_info",
        side_effect=RuntimeError("rollbar down"),
    ):
        try:
            raise ValueError("boom")
        except ValueError:
            zaloguj_polkniety_wyjatek("opis", do_monitoringu=True)

    assert "Nie udało się zgłosić wyjątku do Rollbara" in caplog.text
