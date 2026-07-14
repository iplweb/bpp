# django-pbn-client

Reusable Django models and persistence services for data downloaded from the
Polish Bibliography Network (PBN).

The package deliberately does not define concrete application models or
migrations. Applications subclass `BasePBNMongoDBModel` and retain ownership
of their database schema:

```python
from django.db import models
from django_pbn_client import BasePBNMongoDBModel


class Publication(BasePBNMongoDBModel):
    title = models.TextField(blank=True, default="")
    pull_up_on_save = ["title"]
```

Downloaded objects can then be stored atomically:

```python
from django_pbn_client import download_pbn_objects, upsert_pbn_object

publication = upsert_pbn_object(payload, Publication)
download_pbn_objects(client.get_publications(), Publication)
```

`django-pbn-client` depends only on Django and the transport-level
`pbn-client` package. Progress bars, background jobs, concrete relationships,
and application-specific integration remain the responsibility of the host
application.

Concurrent page downloads use threads by default. The optional
`method="processes"` mode uses the POSIX `fork` start method and is therefore
not available on Windows.

Run the standalone package tests with:

```console
uv run --group dev pytest
```
