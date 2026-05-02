"""Manage testcontainers for BPP test infrastructure.

Starts PostgreSQL (custom iplweb/bpp_dbserver image) and Redis containers
with random ports.  The calling code injects the resolved host:port into
``os.environ`` so Django settings pick them up transparently.

Baseline preload: when ``baseline.sql`` is present (default location
``src/baseline-sql/baseline.sql``, override via ``BPP_BASELINE_SQL_PATH``)
and a fresh PG container is being started, the file is mounted into
``/docker-entrypoint-initdb.d/`` so Postgres' own entrypoint loads it
inside the container — no host ``psql`` required. Combined with
``DATABASES['default']['TEST']['TEMPLATE'] = 'bpp'`` (set up by the
plugin via env), Django then creates ``test_bpp`` via fast in-server
``CREATE DATABASE … WITH TEMPLATE bpp`` instead of replaying the dump.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy
from testcontainers.postgres import PostgresContainer

import docker

logger = logging.getLogger(__name__)

# Fixed names used in reusable mode so containers survive between runs.
_PG_NAME = "bpp-tc-pg"
_REDIS_NAME = "bpp-tc-redis"


def find_baseline_sql() -> Path | None:
    """Locate ``baseline.sql`` for in-container preload.

    Resolution order:
    1. ``$BPP_BASELINE_SQL_PATH`` if set and pointing to an existing file.
    2. Convention: ``<src>/baseline-sql/baseline.sql`` relative to this
       file (``src/testcontainers_bpp/containers.py`` → up one →
       ``src/baseline-sql/baseline.sql``).

    Returns ``None`` when nothing usable is found — caller falls back to
    creating an empty Postgres container.
    """
    override = os.environ.get("BPP_BASELINE_SQL_PATH", "").strip()
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
        logger.warning(
            "BPP_BASELINE_SQL_PATH=%s is set but does not point to a file; "
            "falling back to convention",
            override,
        )

    convention = Path(__file__).resolve().parents[1] / "baseline-sql" / "baseline.sql"
    if convention.is_file():
        return convention
    return None


class DockerNotRunningError(RuntimeError):
    """Raised when the Docker daemon is not reachable."""


def _check_docker_daemon() -> None:
    """Verify Docker daemon is reachable; raise DockerNotRunningError if not."""
    try:
        docker.from_env().ping()
    except docker.errors.DockerException as exc:
        raise DockerNotRunningError(str(exc)) from exc


@dataclass
class BppContainers:
    """Holds references to running containers and their resolved addresses."""

    pg: PostgresContainer | None
    redis: DockerContainer | None

    pg_host: str
    pg_port: int
    redis_host: str
    redis_port: int

    # When True, ``stop_containers`` is a no-op — the user asked the
    # containers to persist between runs (``reuse=True``). Set independently
    # of whether containers were actually found pre-existing, so first-run
    # ``--reuse`` also leaves containers running on exit.
    _persist_on_exit: bool = False


def _find_existing_container(name: str) -> docker.models.containers.Container | None:
    """Return a Docker container by name, starting it if stopped.

    Returns ``None`` only when no container with this name exists. For an
    ``exited``/``created``/``paused`` container, attempts to bring it back
    to ``running`` so the caller can read its (preserved) port mapping.

    Raises ``RuntimeError`` if a container exists but cannot be started —
    most commonly when the host port it was originally bound to is now
    occupied by another process.
    """
    try:
        client = docker.from_env()
        container = client.containers.get(name)
    except docker.errors.NotFound:
        return None
    except docker.errors.APIError:
        logger.exception("Failed to query Docker for container %s", name)
        return None

    if container.status == "running":
        return container

    logger.info("Starting existing container %s (status=%s)", name, container.status)
    try:
        container.start()
        # Refresh attrs so callers reading NetworkSettings.Ports see the
        # current (post-start) mapping rather than stale cached metadata.
        container.reload()
    except docker.errors.APIError as exc:
        raise RuntimeError(
            f"Nie udało się wystartować istniejącego kontenera {name!r}: {exc}\n"
            f"Najczęściej winowajcą jest konflikt portu (host port zajęty "
            f"przez inny proces). Aby zacząć od zera: docker rm -f {name}"
        ) from exc
    return container


def _get_host_port(
    container: docker.models.containers.Container, internal_port: int
) -> tuple[str, int]:
    """Extract the mapped host and port from a running Docker container."""
    ports = container.attrs["NetworkSettings"]["Ports"]
    key = f"{internal_port}/tcp"
    binding = ports.get(key, [{}])[0]
    host = binding.get("HostIp", "localhost")
    if host in ("", "0.0.0.0"):
        host = "localhost"
    return host, int(binding["HostPort"])


def _start_pg(
    reuse: bool, load_baseline: bool = True
) -> tuple[PostgresContainer | None, str, int]:
    """Start PostgreSQL container or reuse an existing one.

    Args:
        reuse: jeśli True, próbuje znaleźć istniejący named container.
        load_baseline: jeśli True (default), montuje ``baseline.sql``
            do init scripts. Ustaw False gdy zamierzasz zrobić własny
            restore na pustej bazie (np. ``pg_restore`` z user-dump-a) —
            inaczej masz zaimportowany baseline przed restore-em i
            ``--clean`` walczy z istniejącymi FK.
    """
    if reuse:
        existing = _find_existing_container(_PG_NAME)
        if existing:
            host, port = _get_host_port(existing, 5432)
            logger.info(
                "Reusing PostgreSQL container %s at %s:%d", _PG_NAME, host, port
            )
            return None, host, port

    pg = PostgresContainer(
        image="iplweb/bpp_dbserver:psql-16.13",
        port=5432,
        username="bpp",
        password="password",
        dbname="bpp",
        driver=None,
    )
    pg.with_env("POSTGRESQL_UNSAFE_BUT_FAST", "1")
    pg.with_env("POSTGRESQL_MAX_LOCKS_PER_TRANSACTION", "512")
    if reuse:
        pg.with_name(_PG_NAME)

    # Defensive: jeśli ktoś kiedyś zbudował iplweb/bpp_dbserver lokalnie przez
    # `docker compose build` (stary workflow), w obraz mogą być wbite labele
    # com.docker.compose.*, przez które Docker Desktop grupowałby testcontainer
    # z kontenerami docker-compose. Nadpisujemy je pustymi na poziomie kontenera.
    pg.with_kwargs(
        labels={
            "com.docker.compose.project": "",
            "com.docker.compose.service": "",
            "com.docker.compose.version": "",
        }
    )

    if load_baseline:
        baseline_sql = find_baseline_sql()
        if baseline_sql is not None:
            # Postgres' entrypoint (docker-entrypoint.sh) replays every
            # ``*.sql`` in /docker-entrypoint-initdb.d/ on first cluster
            # init, before TCP starts accepting connections. testcontainers
            # waits for ``psql -c 'select version()'`` on TCP (see
            # PostgresContainer._connect / ExecWaitStrategy), so by the time
            # pg.start() returns the dump is already loaded.
            pg.with_volume_mapping(
                str(baseline_sql),
                "/docker-entrypoint-initdb.d/01-baseline.sql",
                "ro",
            )
            logger.info("Mounting baseline %s into PG init scripts", baseline_sql)
    else:
        logger.info("Skipping baseline (load_baseline=False)")

    pg.start()

    host = pg.get_container_host_ip()
    port = int(pg.get_exposed_port(5432))
    logger.info("Started PostgreSQL container at %s:%d", host, port)
    return pg, host, port


def _start_redis(reuse: bool) -> tuple[DockerContainer | None, str, int]:
    """Start Redis container or reuse an existing one."""
    if reuse:
        existing = _find_existing_container(_REDIS_NAME)
        if existing:
            host, port = _get_host_port(existing, 6379)
            logger.info("Reusing Redis container %s at %s:%d", _REDIS_NAME, host, port)
            return None, host, port

    redis = DockerContainer("redis:7-alpine")
    redis.with_exposed_ports(6379)
    if reuse:
        redis.with_name(_REDIS_NAME)
    redis.waiting_for(
        LogMessageWaitStrategy("Ready to accept connections").with_startup_timeout(30)
    )
    redis.start()

    host = redis.get_container_host_ip()
    port = int(redis.get_exposed_port(6379))
    logger.info("Started Redis container at %s:%d", host, port)
    return redis, host, port


def start_containers(reuse: bool = False, load_baseline: bool = True) -> BppContainers:
    """Start all service containers.

    When *reuse* is True, containers get fixed names and are kept running
    after pytest exits.  On the next run they are detected and reused
    instead of being recreated.

    When *load_baseline* is False, baseline.sql NIE jest montowane do
    init scripts. Use case: caller chce zrobić własny restore (np.
    ``pg_restore`` z user-supplied dump-a) na pustej bazie.
    """
    _check_docker_daemon()
    print(  # noqa: T201
        f"[testcontainers-bpp] Starting containers "
        f"(reuse={reuse}, load_baseline={load_baseline}) ...",
        file=sys.stderr,
    )
    pg, pg_host, pg_port = _start_pg(reuse, load_baseline=load_baseline)
    redis, redis_host, redis_port = _start_redis(reuse)

    print(  # noqa: T201
        "[testcontainers-bpp] Containers ready: "
        f"pg={pg_host}:{pg_port} "
        f"redis={redis_host}:{redis_port}",
        file=sys.stderr,
    )
    return BppContainers(
        pg=pg,
        redis=redis,
        pg_host=pg_host,
        pg_port=pg_port,
        redis_host=redis_host,
        redis_port=redis_port,
        # reuse=True ⇒ persist on exit, niezależnie od tego czy znaleźliśmy
        # istniejące kontenery, czy stworzyliśmy świeże. Pierwsze uruchomienie
        # z --reuse też zostawia kontenery przy życiu, żeby kolejne mogły je
        # podpiąć.
        _persist_on_exit=reuse,
    )


def stop_containers(containers: BppContainers) -> None:
    """Stop containers unless caller asked them to persist (``reuse=True``)."""
    if containers._persist_on_exit:
        return
    for name, container in [
        ("PostgreSQL", containers.pg),
        ("Redis", containers.redis),
    ]:
        if container is not None:
            try:
                container.stop()
                logger.info("Stopped %s container", name)
            except Exception:
                logger.warning("Failed to stop %s container", name, exc_info=True)
