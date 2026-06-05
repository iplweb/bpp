"""Tests for PBN import websocket routing."""

from pbn_import.routing import websocket_urlpatterns


def test_websocket_route_points_to_import_session_progress():
    pattern = websocket_urlpatterns[0]

    assert len(websocket_urlpatterns) == 1
    assert pattern.pattern.regex.pattern == r"ws/pbn-import/session/(?P<session_id>\w+)/$"
    assert callable(pattern.callback)
