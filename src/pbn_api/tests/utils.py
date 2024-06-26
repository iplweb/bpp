import contextlib
from importlib import import_module

from pbn_api.client import RequestsTransport

from django.contrib.messages.middleware import MessageMiddleware


@contextlib.contextmanager
def middleware(request):
    """Annotate a request object with a session"""

    from django.conf import settings

    engine = import_module(settings.SESSION_ENGINE)
    SessionStore = engine.SessionStore

    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    request.session = SessionStore(session_key)

    # middleware = SessionMiddleware()
    # middleware.process_request(request)
    request.session.save()

    """Annotate a request object with a messages"""
    middleware = MessageMiddleware([])
    middleware.process_request(request)
    request.session.save()
    yield request


class MockTransport(RequestsTransport):
    def __init__(self, return_values=None):
        self.return_values = {}
        self.input_values = {}
        if return_values:
            self.return_values.update(return_values)

    def get(self, url, headers=None):
        if url in self.return_values:
            val = self.return_values.get(url)
            if isinstance(val, Exception):
                raise val
            return val
        else:
            raise ValueError(f"Brak odpowiedzi URL zdefiniowanej dla {url}")

    def post(self, url, headers=None, body=None, delete=False):
        self.input_values[url] = {"headers": headers, "body": body, "delete": delete}
        return self.get(url, headers)
