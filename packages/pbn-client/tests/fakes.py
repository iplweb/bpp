from pbn_client.transport import RequestsTransport


class MockTransport(RequestsTransport):
    def __init__(self, return_values=None, *, reporter=None):
        super().__init__(
            "test-app",
            "test-token",
            "https://pbn-test.example.org",
            "test-user-token",
            reporter=reporter,
        )
        self.return_values = dict(return_values or {})
        self.input_values = {}

    def get(self, url, headers=None, fail_on_auth_missing=False):
        if url not in self.return_values:
            raise ValueError(f"Brak odpowiedzi URL zdefiniowanej dla {url}")

        value = self.return_values[url]
        if isinstance(value, Exception):
            raise value
        return value

    def post(self, url, headers=None, body=None, delete=False):
        self.input_values[url] = {
            "headers": headers,
            "body": body,
            "delete": delete,
        }
        return self.get(url, headers)
