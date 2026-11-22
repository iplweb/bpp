"""Testy :mod:`bpp.zglaszanie_bledow` — wysyłka do Rollbara i/lub Sentry.

Rollbar jest mockowany (``rollbar.report_*``), a „skonfigurowanie" go to token
w ``rollbar.SETTINGS``. Sentry działa naprawdę — SDK jest inicjalizowane
z atrapą transportu, która zbiera wysłane koperty zamiast słać je po sieci.
"""

import logging
import sys
from unittest import mock

import pytest
import rollbar
import sentry_sdk
from sentry_sdk.transport import Transport

from bpp import zglaszanie_bledow
from bpp.zglaszanie_bledow import capture_exception, capture_message


class AtrapaTransportu(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.koperty = []

    def capture_envelope(self, envelope):
        self.koperty.append(envelope)

    @property
    def zdarzenia(self):
        return [k.get_event() for k in self.koperty if k.get_event() is not None]


@pytest.fixture
def sentry():
    """Sentry zainicjalizowane z atrapą transportu; sprzątane po teście."""
    transport = AtrapaTransportu()
    sentry_sdk.init(
        dsn="https://klucz@glitchtip.invalid/1",
        transport=transport,
        default_integrations=False,
        auto_enabling_integrations=False,
    )
    yield transport
    sentry_sdk.get_global_scope().set_client(None)


@pytest.fixture
def rollbar_mock(rollbar_skonfigurowany):
    with (
        mock.patch.object(rollbar, "report_exc_info") as exc,
        mock.patch.object(rollbar, "report_message") as msg,
    ):
        yield mock.Mock(report_exc_info=exc, report_message=msg)


@pytest.fixture
def rollbar_bez_tokenu(monkeypatch):
    monkeypatch.setitem(rollbar.SETTINGS, "access_token", None)
    with (
        mock.patch.object(rollbar, "report_exc_info") as exc,
        mock.patch.object(rollbar, "report_message") as msg,
    ):
        yield mock.Mock(report_exc_info=exc, report_message=msg)


def _rzuc_i_zglos(**kwargs):
    try:
        raise ValueError("boom-testowy")
    except ValueError:
        capture_exception(**kwargs)


def test_bez_sentry_dsn_sentry_nieaktywny():
    assert not zglaszanie_bledow.sentry_skonfigurowany()


def test_oba_backendy_dostaja_wyjatek(rollbar_mock, sentry):
    _rzuc_i_zglos(level="warning", extra={"pk": 5}, tags={"faza": "test"})

    rollbar_mock.report_exc_info.assert_called_once()
    args, kwargs = rollbar_mock.report_exc_info.call_args
    assert isinstance(args[0][1], ValueError)
    assert kwargs["level"] == "warning"
    assert kwargs["extra_data"] == {"pk": 5, "tags": {"faza": "test"}}

    (zdarzenie,) = sentry.zdarzenia
    assert zdarzenie["exception"]["values"][-1]["value"] == "boom-testowy"
    assert zdarzenie["level"] == "warning"
    assert zdarzenie["extra"]["pk"] == 5
    assert zdarzenie["tags"]["faza"] == "test"


def test_extra_bez_tagow_idzie_do_rollbara_bez_zmian(rollbar_mock):
    _rzuc_i_zglos()
    assert rollbar_mock.report_exc_info.call_args.kwargs["extra_data"] is None

    dane = {"a": 1}
    _rzuc_i_zglos(extra=dane)
    assert rollbar_mock.report_exc_info.call_args.kwargs["extra_data"] is dane


def test_tylko_rollbar(rollbar_mock):
    _rzuc_i_zglos(extra={"pk": 1})

    rollbar_mock.report_exc_info.assert_called_once()
    assert not zglaszanie_bledow.sentry_skonfigurowany()


def test_tylko_sentry(rollbar_bez_tokenu, sentry):
    _rzuc_i_zglos(extra={"pk": 1})

    rollbar_bez_tokenu.report_exc_info.assert_not_called()
    assert len(sentry.zdarzenia) == 1


def test_nic_nie_skonfigurowane_to_no_op(rollbar_bez_tokenu):
    _rzuc_i_zglos()
    capture_message("komunikat", level="warning")

    rollbar_bez_tokenu.report_exc_info.assert_not_called()
    rollbar_bez_tokenu.report_message.assert_not_called()


def test_blad_rollbara_nie_blokuje_sentry(rollbar_mock, sentry, caplog):
    rollbar_mock.report_exc_info.side_effect = RuntimeError("rollbar leży")
    caplog.set_level(logging.ERROR, logger="bpp.zglaszanie_bledow")

    _rzuc_i_zglos()

    assert len(sentry.zdarzenia) == 1
    assert "Nie udało się zgłosić wyjątku do Rollbara" in caplog.text
    assert "rollbar leży" in caplog.text


def test_blad_sentry_nie_blokuje_rollbara_ani_wolajacego(rollbar_mock, sentry, caplog):
    caplog.set_level(logging.ERROR, logger="bpp.zglaszanie_bledow")
    with mock.patch.object(
        sentry_sdk, "capture_exception", side_effect=RuntimeError("sentry leży")
    ):
        _rzuc_i_zglos()

    rollbar_mock.report_exc_info.assert_called_once()
    assert "Nie udało się zgłosić wyjątku do Sentry" in caplog.text


def test_blad_sentry_w_komunikacie_nie_wybucha(rollbar_mock, sentry, caplog):
    caplog.set_level(logging.ERROR, logger="bpp.zglaszanie_bledow")
    with mock.patch.object(
        sentry_sdk, "capture_message", side_effect=RuntimeError("sentry leży")
    ):
        capture_message("komunikat", level="error")

    rollbar_mock.report_message.assert_called_once()
    assert "Nie udało się zgłosić komunikatu do Sentry" in caplog.text


def test_jawne_exc_info_poza_blokiem_except(rollbar_mock, sentry):
    try:
        raise KeyError("klucz")
    except KeyError:
        exc_info = sys.exc_info()

    capture_exception(exc_info)

    assert rollbar_mock.report_exc_info.call_args.args[0] is exc_info
    (zdarzenie,) = sentry.zdarzenia
    assert zdarzenie["exception"]["values"][-1]["type"] == "KeyError"


def test_pomin_sentry(rollbar_mock, sentry):
    _rzuc_i_zglos(pomin_sentry=True)

    rollbar_mock.report_exc_info.assert_called_once()
    assert sentry.zdarzenia == []


def test_request_trafia_do_rollbara(rollbar_mock, rf):
    request = rf.get("/")
    _rzuc_i_zglos(request=request)
    assert rollbar_mock.report_exc_info.call_args.kwargs["request"] is request


def test_komunikat_do_obu(rollbar_mock, sentry):
    capture_message("Coś dziwnego", level="warning", extra={"ile": 3})

    rollbar_mock.report_message.assert_called_once_with(
        "Coś dziwnego", level="warning", request=None, extra_data={"ile": 3}
    )
    (zdarzenie,) = sentry.zdarzenia
    assert zdarzenie["message"] == "Coś dziwnego"
    assert zdarzenie["level"] == "warning"
    assert zdarzenie["extra"]["ile"] == 3


def test_komunikat_domyslnie_info(rollbar_mock, sentry):
    capture_message("Informacja")

    assert rollbar_mock.report_message.call_args.kwargs["level"] == "info"
    assert sentry.zdarzenia[0]["level"] == "info"


def test_critical_to_fatal_w_sentry(rollbar_bez_tokenu, sentry):
    capture_message("Awaria", level="critical")
    assert sentry.zdarzenia[0]["level"] == "fatal"


def test_extra_i_tagi_nie_wyciekaja_do_kolejnych_zgloszen(rollbar_bez_tokenu, sentry):
    capture_message("pierwszy", extra={"tajne": 1}, tags={"t": "x"})
    capture_message("drugi")

    drugi = sentry.zdarzenia[1]
    assert "tajne" not in drugi.get("extra", {})
    assert "t" not in drugi.get("tags", {})
