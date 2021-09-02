import contextlib

from pbn_api.client import RequestsTransport

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware


@contextlib.contextmanager
def middleware(request):
    """Annotate a request object with a session"""
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()

    """Annotate a request object with a messages"""
    middleware = MessageMiddleware()
    middleware.process_request(request)
    request.session.save()
    yield request


class MockTransport(RequestsTransport):
    def __init__(self, return_values=None):
        self.return_values = {}
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
        return self.get(url, headers)
