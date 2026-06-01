"""Fixtures dla testów demo_data."""

import pytest


@pytest.fixture
def tmp_manifest_path(tmp_path):
    """Ścieżka do pliku manifestu w tmpdirze pytesta."""
    return tmp_path / "demo_manifest.json"


@pytest.fixture
def rng():
    """Deterministyczny RNG dla testów (seed=42)."""
    import random

    return random.Random(42)
