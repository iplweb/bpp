"""Fail-closed guard placeholdera ALTCHA_HMAC_KEY w ustawieniach produkcyjnych."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from django_bpp.settings.altcha_key_guard import (
    altcha_klucz_niebezpieczny_placeholder,
)

SENTINEL = "Please set the ALTCHA_HMAC_KEY variable."
SRC_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "klucz,oczekiwane",
    [
        ("", True),
        (SENTINEL, True),
        ("ZMIEN_KONIECZNIE_PRZED_URUCHOMIENIEM", True),
        ("build-time-only-not-used", True),
        ("5f0c1e2d3b4a69788796a5b4c3d2e1f00f1e2d3c4b5a6978", False),
    ],
)
def test_wykrywanie_placeholdera_altcha(klucz, oczekiwane):
    assert (
        altcha_klucz_niebezpieczny_placeholder(klucz, unset_sentinel=SENTINEL)
        is oczekiwane
    )


def _importuj_production(**env_extra):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "DJANGO_BPP_SKIP_DOTENV": "1",
        "DJANGO_BPP_SECRET_KEY": "k9q7wR4tY6uI8oP1aS3dF5gH0jL2xC4vB6nM8-test",
        **env_extra,
    }
    return subprocess.run(
        [sys.executable, "-c", "import django_bpp.settings.production"],
        cwd=SRC_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "env_extra,ma_przejsc",
    [
        # CAPTCHA włączona bez klucza / z placeholderem → produkcja nie wstaje.
        ({"ZGLOS_CAPTCHA_ENABLED": "1"}, False),
        ({"ZGLOS_CAPTCHA_ENABLED": "1", "ALTCHA_HMAC_KEY": "ZMIEN_TO"}, False),
        # CAPTCHA włączona z realnym kluczem → OK.
        (
            {
                "ZGLOS_CAPTCHA_ENABLED": "1",
                "ALTCHA_HMAC_KEY": "5f0c1e2d3b4a69788796a5b4c3d2e1f0",
            },
            True,
        ),
        # CAPTCHA wyłączona (domyślnie, np. build obrazu) → klucz bez znaczenia.
        ({}, True),
    ],
)
def test_production_fail_closed_altcha(env_extra, ma_przejsc):
    wynik = _importuj_production(**env_extra)
    if ma_przejsc:
        assert wynik.returncode == 0, wynik.stderr
    else:
        assert wynik.returncode != 0
        assert "ImproperlyConfigured" in wynik.stderr
        assert "ALTCHA_HMAC_KEY" in wynik.stderr
