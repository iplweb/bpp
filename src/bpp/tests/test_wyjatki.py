"""Testy helpera :func:`bpp.util.zaloguj_polkniety_wyjatek`."""

import logging
from unittest import mock

from bpp.util import zaloguj_polkniety_wyjatek


def test_loguje_pelny_traceback(caplog):
    caplog.set_level(logging.ERROR)
    try:
        raise ValueError("boom")
    except ValueError:
        zaloguj_polkniety_wyjatek("Coś padło przy X", do_rollbar=False)

    assert "Coś padło przy X" in caplog.text
    # logger.exception -> traceback z oryginalnym wyjątkiem
    assert "ValueError" in caplog.text
    assert "boom" in caplog.text


def test_uzywa_przekazanego_loggera():
    logger = mock.Mock()
    try:
        raise KeyError("k")
    except KeyError:
        zaloguj_polkniety_wyjatek("opis", logger=logger, do_rollbar=False)

    logger.exception.assert_called_once_with("opis")


def test_raportuje_do_rollbara_gdy_wlaczony():
    with mock.patch("bpp.util.wyjatki.rollbar") as rb:
        try:
            raise RuntimeError("x")
        except RuntimeError:
            zaloguj_polkniety_wyjatek("opis", do_rollbar=True)
        rb.report_exc_info.assert_called_once()


def test_nie_raportuje_do_rollbara_gdy_wylaczony():
    with mock.patch("bpp.util.wyjatki.rollbar") as rb:
        try:
            raise RuntimeError("x")
        except RuntimeError:
            zaloguj_polkniety_wyjatek("opis", do_rollbar=False)
        rb.report_exc_info.assert_not_called()


def test_blad_rollbara_nie_wybucha(caplog):
    with mock.patch("bpp.util.wyjatki.rollbar") as rb:
        rb.report_exc_info.side_effect = RuntimeError("rollbar down")
        try:
            raise ValueError("boom")
        except ValueError:
            # nie powinno podnieść wyjątku z rollbara
            zaloguj_polkniety_wyjatek("opis", do_rollbar=True)
