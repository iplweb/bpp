"""Broker connectivity probe for the celerybeat healthcheck.

Beat publishes scheduled tasks to the broker (RabbitMQ); if the broker is
unreachable, beat keeps running but silently fails to enqueue work. This
script opens a fresh AMQP connection and exits non-zero on failure so the
Docker HEALTHCHECK can flag the container as unhealthy.

It does NOT depend on any worker being up (unlike `celery inspect`/`status`).
"""

import sys

CONNECT_TIMEOUT = 5


def main() -> int:
    try:
        from django_bpp.celery_tasks import app
    except Exception as exc:
        print(f"celerybeat: cannot import celery app: {exc!r}", file=sys.stderr)
        return 2

    try:
        with app.connection(connect_timeout=CONNECT_TIMEOUT) as conn:
            conn.connect()
    except Exception as exc:
        print(f"celerybeat: broker unreachable: {exc!r}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
