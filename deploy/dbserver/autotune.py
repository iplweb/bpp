#!/usr/bin/env python
# This script is based on pgtune, and generates a configuration based on
# Aptible's APTIBLE_CONTAINER_SIZE environment variable (size in MB).
# ... with some fixes from yours truly (mpasternak)

import os
import sys

ONE_MB_IN_KB = 1024
ONE_GB_IN_KB = 1024 * ONE_MB_IN_KB

how_much_ram_for_postgres = float(os.environ.get("POSTGRESQL_RAM_PERCENT", "0.5"))
force_ram_for_postgres = os.environ.get("POSTGRESQL_RAM_THIS_MUCH_GB", None)
default_ram_for_postgres = 4096


def total_ram_size_mb():
    if force_ram_for_postgres:
        return int(force_ram_for_postgres)

    import re

    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as f:
            meminfo = f.read()
        matched = re.search(r"^MemTotal:\s+(\d+)", meminfo)
        if matched:
            mem_total_kB = int(matched.groups()[0])
            return how_much_ram_for_postgres * mem_total_kB / 1024

    return default_ram_for_postgres


def normalize_size(v):
    if v % ONE_GB_IN_KB == 0:
        return f"{int(v / ONE_GB_IN_KB)}GB"

    if v % ONE_MB_IN_KB == 0:
        return f"{int(v / ONE_MB_IN_KB)}MB"

    return f"{int(v)}kB"


def to_config_value(v):
    if isinstance(v, str):
        return v

    if isinstance(v, int):
        return normalize_size(v)

    if isinstance(v, float):
        return to_config_value(int(v))

    raise TypeError(f"Unexpected type: {type(v)}")


def generate_config(ram_kb):
    config = {}

    # Directly form pgtune
    config["shared_buffers"] = ram_kb / 4
    config["effective_cache_size"] = ram_kb * 3 / 4
    config["maintenance_work_mem"] = min(ram_kb / 16, 2 * ONE_GB_IN_KB)

    # We're tweaking this a little bit here. While we allow up to 250
    # connections (because we've frequently seen customers with leaky or
    # misconfigured connection pools), we assume 50 per GB.
    conns = 50
    config["work_mem"] = (ram_kb * 3 / 4) / (conns * 3)

    config["min_wal_size"] = ONE_GB_IN_KB
    config["max_wal_size"] = 2 * ONE_GB_IN_KB

    config["wal_buffers"] = min(ram_kb * 3 / 4 / 100, 16 * ONE_MB_IN_KB)

    config["checkpoint_completion_target"] = "0.7"
    config["default_statistics_target"] = "100"

    return {x: to_config_value(y) for x, y in config.items()}


def main():
    ram_mb = total_ram_size_mb()
    config = generate_config(ram_mb * ONE_MB_IN_KB)
    print("# Automatically added by autotune.py")
    for k, v in sorted(config.items()):
        print(f"{k} = {v}")


def test():
    test_cases = [
        [
            0.5 * ONE_GB_IN_KB,
            {
                "shared_buffers": "128MB",
                "effective_cache_size": "384MB",
                "work_mem": "2621kB",
                "maintenance_work_mem": "32MB",
                "min_wal_size": "1GB",
                "max_wal_size": "2GB",
                "checkpoint_completion_target": "0.7",
                "wal_buffers": "3932kB",
                "default_statistics_target": "100",
            },
        ],
        [
            ONE_GB_IN_KB,
            {
                "shared_buffers": "256MB",
                "effective_cache_size": "768MB",
                "work_mem": "5242kB",
                "maintenance_work_mem": "64MB",
                "min_wal_size": "1GB",
                "max_wal_size": "2GB",
                "checkpoint_completion_target": "0.7",
                "wal_buffers": "7864kB",
                "default_statistics_target": "100",
            },
        ],
        [
            2 * ONE_GB_IN_KB,
            {
                "shared_buffers": "512MB",
                "effective_cache_size": "1536MB",
                "work_mem": "10485kB",
                "maintenance_work_mem": "128MB",
                "min_wal_size": "1GB",
                "max_wal_size": "2GB",
                "checkpoint_completion_target": "0.7",
                "wal_buffers": "15728kB",
                "default_statistics_target": "100",
            },
        ],
        [
            4 * ONE_GB_IN_KB,
            {
                "shared_buffers": "1GB",
                "effective_cache_size": "3GB",
                "work_mem": "20971kB",
                "maintenance_work_mem": "256MB",
                "min_wal_size": "1GB",
                "max_wal_size": "2GB",
                "checkpoint_completion_target": "0.7",
                "wal_buffers": "16MB",
                "default_statistics_target": "100",
            },
        ],
    ]

    for size, expected_config in test_cases:
        prefix = f"Postgres at {size / ONE_GB_IN_KB}GB"

        real_config = generate_config(size)

        real_keys = sorted(real_config.keys())
        expected_keys = sorted(expected_config.keys())

        m = "{}: keys differ\n  Got: {}\n  Expected: {}".format(
            prefix, real_keys, expected_keys
        )
        assert real_keys == expected_keys, m

        for key, expected in expected_config.items():
            real = real_config[key]
            m = "{}: {} differs:\n  Got: {}\n  Expected: {}".format(
                prefix, key, real, expected
            )
            assert real == expected, m

    sys.stderr.write("OK\n")


def usage(program):
    sys.stderr.write(f"Usage: {program} [--test]\n")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()
    elif len(sys.argv) == 2 and sys.argv[1] == "--test":
        test()
    else:
        usage(sys.argv[0])
