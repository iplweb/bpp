"""Regression: X-Accel-Redirect responses must declare their real body length.

On production (ASGI, uvicorn) every ``GET /favicon.ico`` logged
"Exception in ASGI application ... RuntimeError: Response content shorter than
Content-Length". ``django_sendfile.sendfile`` sets ``Content-Length`` to the
file size even for the ``nginx`` backend, whose body is empty (nginx serves
the file after ``X-Accel-Redirect``). uvicorn refuses to finish a response
whose body is shorter than the declared length.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django_sendfile.utils import _get_sendfile

from django_bpp import asgi
from django_bpp.middleware import OffloadedFileContentLengthMiddleware

NGINX_BACKEND = "django_sendfile.backends.nginx"
FAVICON = b"\x00\x00\x01\x00" + b"x" * 4064


@pytest.fixture
def nginx_sendfile(settings):
    settings.SENDFILE_BACKEND = NGINX_BACKEND
    _get_sendfile.cache_clear()
    yield
    _get_sendfile.cache_clear()


@pytest.fixture
def favicon_file(settings):
    path = Path(settings.MEDIA_ROOT) / "favicon" / "test-content-length.ico"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(FAVICON)
    cache.clear()  # /favicon.ico is wrapped in cache_page
    # Patch the manager class, not ``Uczelnia.objects``: Django hands out copies
    # of managers (Options.managers_map), which are rebuilt when the app
    # registry cache is cleared, so a patched instance attribute can be lost.
    with mock.patch(
        "bpp.models.uczelnia.UczelniaManager.get",
        return_value=SimpleNamespace(favicon_ico=SimpleNamespace(path=str(path))),
    ):
        yield path
    path.unlink()
    cache.clear()


async def _asgi_get(path):
    """Run one GET through the ASGI app; return (headers, body)."""
    messages = []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    request_sent = False

    async def receive():
        # Django reads the body, then keeps calling receive() to detect a client
        # disconnect. A second http.request trips its assertion, cancels the
        # request and deadlocks ThreadSensitiveContext; a client that is still
        # connected simply sends nothing more.
        nonlocal request_sent
        if request_sent:
            await asyncio.Event().wait()
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await asgi.application(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    return {k.lower(): v for k, v in start["headers"]}, body


@pytest.mark.django_db(transaction=True)
def test_favicon_przez_asgi_content_length_zgodny_z_trescia(
    nginx_sendfile, favicon_file
):
    """uvicorn's check: declared Content-Length must equal the bytes sent."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        headers, body = pool.submit(asyncio.run, _asgi_get("/favicon.ico")).result()

    assert headers[b"x-accel-redirect"] == b"/media/favicon/test-content-length.ico"
    assert int(headers[b"content-length"]) == len(body)


@pytest.mark.django_db
def test_favicon_przez_klienta_content_length_zgodny_z_trescia(
    client, nginx_sendfile, favicon_file
):
    for _ in range(2):  # second hit comes from the cache_page entry
        response = client.get("/favicon.ico")
        assert response.status_code == 200
        assert response.has_header("X-Accel-Redirect"), response.content[:200]
        assert int(response["Content-Length"]) == len(response.content)


@pytest.mark.parametrize("naglowek", ["X-Accel-Redirect", "X-Sendfile"])
def test_middleware_poprawia_content_length_odpowiedzi_offload(naglowek):
    response = HttpResponse()
    response[naglowek] = "/media/protected/plik.pdf"
    response["Content-Length"] = "123456"

    middleware = OffloadedFileContentLengthMiddleware(lambda request: response)
    wynik = middleware(RequestFactory().get("/"))

    assert wynik["Content-Length"] == "0"


def test_middleware_nie_rusza_zwyklych_odpowiedzi():
    response = HttpResponse(b"abc")
    response["Content-Length"] = "999"  # not ours to judge without offload

    middleware = OffloadedFileContentLengthMiddleware(lambda request: response)

    assert middleware(RequestFactory().get("/"))["Content-Length"] == "999"


@override_settings(SENDFILE_BACKEND="django_sendfile.backends.simple")
@pytest.mark.django_db
def test_simple_backend_dalej_wysyla_plik(client, favicon_file):
    _get_sendfile.cache_clear()
    try:
        response = client.get("/favicon.ico")
        body = response.content
    finally:
        _get_sendfile.cache_clear()

    assert body == FAVICON
    assert int(response["Content-Length"]) == len(FAVICON)
