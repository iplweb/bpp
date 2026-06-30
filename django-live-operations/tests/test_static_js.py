"""
Smoke tests for the live-operations.js static file.

Asserts:
- File exists at the expected static path.
- File contains the required plugin integration points.
"""
from pathlib import Path

import live_operations

STATIC_JS = (
    Path(live_operations.__file__).parent
    / "static"
    / "live_operations"
    / "live-operations.js"
)


def test_js_file_exists():
    """live-operations.js is present in the package static directory."""
    assert STATIC_JS.exists(), f"Expected JS file at {STATIC_JS}"
    assert STATIC_JS.is_file()


def test_js_contains_liveop_html():
    """Plugin handles msg.liveop_html (§19.2 envelope key)."""
    content = STATIC_JS.read_text()
    assert "liveop_html" in content


def test_js_calls_channelsBroadcast_init():
    """Plugin initialises channels_broadcast socket via channelsBroadcast.init."""
    content = STATIC_JS.read_text()
    assert "channelsBroadcast.init" in content


def test_js_calls_htmx_process():
    """Plugin calls htmx.process() after OOB-swap so hx-* attrs activate."""
    content = STATIC_JS.read_text()
    assert "htmx.process" in content


def test_js_contains_liveop_chain():
    """Plugin handles msg.liveop_chain for chain_to() support."""
    content = STATIC_JS.read_text()
    assert "liveop_chain" in content


def test_js_reads_data_liveop_token():
    """Plugin reads the subscription token from data-liveop-token attribute."""
    content = STATIC_JS.read_text()
    assert "data-liveop-token" in content


def test_js_passes_subscription_token_to_init():
    """Plugin passes subscriptionToken to channelsBroadcast.init."""
    content = STATIC_JS.read_text()
    assert "subscriptionToken" in content
