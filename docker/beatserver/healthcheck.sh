#!/bin/sh -e
# Healthcheck for celerybeat.
#
# Two-stage probe (both must pass):
#   1. Liveness: process listed in /celerybeat.pid is alive. Beat doesn't
#      expose an `inspect` channel (that's a worker thing), so we go via
#      the pidfile that `celery beat --pidfile=/celerybeat.pid` writes.
#   2. Broker: a fresh AMQP connection to RabbitMQ succeeds. Beat keeps
#      running even when the broker is down (it just fails to publish),
#      so a process-only check would be a false positive.

PID_FILE=/celerybeat.pid

if [ ! -s "$PID_FILE" ]; then
    echo "celerybeat: pidfile $PID_FILE missing or empty" >&2
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "celerybeat: process $PID not running" >&2
    exit 1
fi

exec python /app/healthcheck_broker.py
