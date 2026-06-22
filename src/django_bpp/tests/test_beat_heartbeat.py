import os
from unittest import mock

from django_bpp import beat_heartbeat


def test_write_heartbeat_creates_file(tmp_path):
    f = tmp_path / "beat.alive"
    assert beat_heartbeat.write_heartbeat(f) is True
    assert f.exists()


def test_write_heartbeat_refreshes_mtime(tmp_path):
    f = tmp_path / "beat.alive"
    f.touch()
    os.utime(f, (1000, 1000))  # cofnij mtime daleko w przeszlosc
    beat_heartbeat.write_heartbeat(f)
    assert f.stat().st_mtime > 1000


def test_write_heartbeat_returns_false_on_error(tmp_path):
    # rodzic nie istnieje -> touch rzuca OSError, ma byc zalogowane i False (beat zyje)
    f = tmp_path / "nie-ma-katalogu" / "beat.alive"
    assert beat_heartbeat.write_heartbeat(f) is False


def test_cap_interval_limits_long_idle_sleep():
    assert beat_heartbeat.cap_interval(300) == beat_heartbeat.HEARTBEAT_INTERVAL


def test_cap_interval_keeps_short_interval():
    assert beat_heartbeat.cap_interval(2) == 2


def test_tick_touches_heartbeat_and_caps_interval(tmp_path, monkeypatch):
    f = tmp_path / "beat.alive"
    monkeypatch.setattr(beat_heartbeat, "HEARTBEAT_FILE", f)
    # __new__ pomija __init__ (wymagajacy aplikacji celery) - testujemy sam tick().
    sched = beat_heartbeat.HeartbeatScheduler.__new__(beat_heartbeat.HeartbeatScheduler)
    with mock.patch(
        "celery.beat.PersistentScheduler.tick", return_value=300
    ) as super_tick:
        interval = sched.tick()
    super_tick.assert_called_once()
    assert f.exists()
    assert interval == beat_heartbeat.HEARTBEAT_INTERVAL
