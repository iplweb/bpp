from django_bpp.celery_tasks import resolve_worker_config


def test_linux_prefork_defaults_to_75_percent_of_cores():
    cfg = resolve_worker_config(environ={}, system="Linux", cpu_count=8)
    assert cfg["worker_pool"] == "prefork"
    assert cfg["worker_concurrency"] == 6  # floor(8 * 0.75)
    assert "worker_max_tasks_per_child" not in cfg
    assert "worker_max_memory_per_child" not in cfg
    assert "worker_prefetch_multiplier" not in cfg


def test_macos_defaults_to_threads_pool_concurrency_10():
    cfg = resolve_worker_config(environ={}, system="Darwin", cpu_count=10)
    assert cfg["worker_pool"] == "threads"
    assert cfg["worker_concurrency"] == 10


def test_macos_prefork_override_uses_percent():
    cfg = resolve_worker_config(
        environ={"CELERY_USE_PREFORK": "1"}, system="Darwin", cpu_count=8
    )
    assert cfg["worker_pool"] == "prefork"
    assert cfg["worker_concurrency"] == 6


def test_explicit_concurrency_wins_over_percent():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_CONCURRENCY": "3"}, system="Linux", cpu_count=8
    )
    assert cfg["worker_concurrency"] == 3


def test_concurrency_percent_env_overrides_default_75():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_CONCURRENCY_PERCENT": "50"},
        system="Linux",
        cpu_count=8,
    )
    assert cfg["worker_concurrency"] == 4  # floor(8 * 0.50)


def test_concurrency_never_below_one():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_CONCURRENCY_PERCENT": "10"},
        system="Linux",
        cpu_count=1,
    )
    assert cfg["worker_concurrency"] == 1  # max(1, floor(0.1)) -> 1


def test_explicit_pool_override():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_POOL": "gevent"}, system="Linux", cpu_count=8
    )
    assert cfg["worker_pool"] == "gevent"
    assert cfg["worker_concurrency"] == 6


def test_optional_memory_and_prefetch_knobs_passed_through():
    cfg = resolve_worker_config(
        environ={
            "CELERY_WORKER_PREFETCH_MULTIPLIER": "1",
            "CELERY_WORKER_MAX_TASKS_PER_CHILD": "100",
            "CELERY_WORKER_MAX_MEMORY_PER_CHILD": "500000",
        },
        system="Linux",
        cpu_count=4,
    )
    assert cfg["worker_prefetch_multiplier"] == 1
    assert cfg["worker_max_tasks_per_child"] == 100
    assert cfg["worker_max_memory_per_child"] == 500000


def test_concurrency_floors_to_honor_maximum_75_percent():
    # "maksymalnie 75%": 10 * 0.75 = 7.5 -> floor -> 7 (70%), never 8 (80%).
    cfg = resolve_worker_config(environ={}, system="Linux", cpu_count=10)
    assert cfg["worker_concurrency"] == 7
