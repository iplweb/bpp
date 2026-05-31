"""Single source of truth for the ``channels_redis`` key prefix.

``channels_redis`` namespaces every group key as ``{prefix}:group:{name}``
(default prefix ``"asgi"`` — see ``RedisChannelLayer._group_key``). Under
``pytest -n auto`` all xdist workers share one Redis testcontainer, and the
per-user group name is ``md5(pk + username)`` — which collides across workers
because ``transactional_db`` resets PK sequences (``TRUNCATE ... RESTART
IDENTITY``) and the test username is constant. Without a per-worker prefix,
consumers spawned by different workers land in the *same* Redis group, so one
worker's ``group_send`` fans out to another worker's channels and the
WebSocket message is probabilistically lost (see
``docs/CHANNELS_BROADCAST_FLAKE.md``).

Two cooperating processes must agree on the prefix byte-for-byte:

- the Daphne subprocess, via ``CHANNEL_LAYERS`` in settings, and
- the test-side subscription poller ``wait_for_channel_subscription``
  (``django_bpp.playwright_util``), which reads the group key directly from
  Redis.

If they disagree, the poller watches the wrong key and times out. This module
is that single source of truth — keep it dependency-light (stdlib only) so it
is safe to import from Django settings.
"""

import os

#: The upstream ``channels_redis`` default prefix; also the production value.
DEFAULT_CHANNELS_PREFIX = "asgi"

#: Explicit override env var, honoured in any environment.
CHANNELS_PREFIX_ENV = "DJANGO_BPP_CHANNELS_PREFIX"


def get_channels_prefix() -> str:
    """Return the ``channels_redis`` key prefix for the current process.

    Resolution order:

    1. ``DJANGO_BPP_CHANNELS_PREFIX`` — explicit override (any environment).
    2. ``asgi-test-<worker>`` when running under pytest-xdist
       (``PYTEST_XDIST_WORKER`` is set) — isolates each worker's namespace so
       colliding per-user group names cannot cross-talk between workers.
    3. ``"asgi"`` — the ``channels_redis`` default (production / non-xdist).

    Both the Daphne subprocess (spawned from the xdist worker, inheriting its
    environment) and the pytest worker import this module, so they compute the
    identical prefix.
    """
    explicit = os.environ.get(CHANNELS_PREFIX_ENV)
    if explicit:
        return explicit

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        return f"{DEFAULT_CHANNELS_PREFIX}-test-{worker}"

    return DEFAULT_CHANNELS_PREFIX
