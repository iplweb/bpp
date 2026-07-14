# pbn-client

`pbn-client` is a framework-independent Python client for communication with
the Polish Bibliography Network (PBN) API. It provides HTTP authentication,
pagination, dictionary and publication endpoints, and institution-profile
statement operations.

The package does not depend on Django or an external error-reporting service.
Projects that persist downloaded PBN data in Django should use the companion
`django-pbn-client` package.

## Installation

```console
pip install pbn-client
```

Python 3.10 through 3.14 is supported.

## Basic usage

```python
from pbn_client import PBNClient, RequestsTransport

transport = RequestsTransport(
    app_id="application-id",
    app_token="application-token",
    base_url="https://pbn-micro-alpha.opi.org.pl",
    user_token="user-token",
    timeout=(30, 120),
)
client = PBNClient(transport)

languages = list(client.get_languages())
```

Credentials should normally be supplied explicitly. The interactive command
helpers also understand `PBN_CLIENT_APP_ID`, `PBN_CLIENT_APP_TOKEN`,
`PBN_CLIENT_BASE_URL`, `PBN_CLIENT_USER_TOKEN`, and
`PBN_CLIENT_HTTP_TIMEOUT`. A timeout may be a single number or a
`connect,read` pair.

## Error reporting

The standalone default reporter is a no-op. An application can inject any
object implementing `ErrorReporter` when it constructs a transport:

```python
import rollbar

from pbn_client import RequestsTransport

transport = RequestsTransport(
    "application-id",
    "application-token",
    "https://pbn-micro-alpha.opi.org.pl",
    reporter=rollbar,
)
```

The reporter receives only scrubbed diagnostic metadata. Response bodies and
authentication header values are not sent to it. `LoggingReporter`,
`NullReporter`, and `set_default_reporter()` are also available for applications
that prefer a process-wide policy.

## Development

From the repository root:

```console
uv run --project packages/pbn-client pytest
uv run ruff check packages/pbn-client
uv build --project packages/pbn-client
```
