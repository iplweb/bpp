"""Testy predykatu fail-closed guard SECRET_KEY (#4 z security review)."""

import pytest

from django_bpp.settings.secret_key_guard import (
    SECRET_KEY_BUILD_DUMMY,
    secret_key_niebezpieczny_placeholder,
    tryb_buildu,
)

# Sentinel z base.py (default gdy env DJANGO_BPP_SECRET_KEY nieustawiony).
SENTINEL = "Please set the DJANGO_BPP_SECRET_KEY variable."


@pytest.mark.parametrize(
    "key,oczekiwane",
    [
        # Realne misdeploye — MUSZĄ zablokować start produkcji.
        ("", True),
        (SENTINEL, True),
        ("ZMIEN_KONIECZNIE_PRZED_URUCHOMIENIEM_PRODUKCJI", True),
        # Publicznie znana wartość z Dockerfile — poza buildem odrzucana.
        (SECRET_KEY_BUILD_DUMMY, True),
        # Wartości bezpieczne — produkcja wstaje normalnie.
        ("k9$2mZ!q7wR4tY6uI8oP1aS3dF5gH0jL2xC4vB6nM8", False),
    ],
)
def test_wykrywanie_placeholdera_secret_key(key, oczekiwane):
    assert (
        secret_key_niebezpieczny_placeholder(key, unset_sentinel=SENTINEL) is oczekiwane
    )


def test_wartosc_buildowa_przepuszczana_tylko_w_trybie_buildu():
    """Wyjątek dla collectstatic w buildzie obrazu: tylko przy jawnym
    ``build_stage=True`` (``DJANGO_BPP_BUILD_STAGE=1`` inline w RUN-ie)."""
    assert (
        secret_key_niebezpieczny_placeholder(
            SECRET_KEY_BUILD_DUMMY, unset_sentinel=SENTINEL, build_stage=True
        )
        is False
    )


@pytest.mark.parametrize(
    "key", ["", SENTINEL, "ZMIEN_KONIECZNIE_PRZED_URUCHOMIENIEM_PRODUKCJI"]
)
def test_tryb_buildu_nie_przepuszcza_innych_placeholderow(key):
    assert (
        secret_key_niebezpieczny_placeholder(
            key, unset_sentinel=SENTINEL, build_stage=True
        )
        is True
    )


@pytest.mark.parametrize(
    "environ,oczekiwane",
    [
        ({}, False),
        ({"DJANGO_BPP_BUILD_STAGE": "0"}, False),
        ({"DJANGO_BPP_BUILD_STAGE": "true"}, False),
        ({"DJANGO_BPP_BUILD_STAGE": "1"}, True),
    ],
)
def test_tryb_buildu_z_env(environ, oczekiwane):
    assert tryb_buildu(environ) is oczekiwane


def test_dockerfile_ustawia_tryb_buildu_przy_collectstatic_z_dummy_kluczem():
    """Każdy RUN z dummy kluczem musi też ustawiać DJANGO_BPP_BUILD_STAGE=1,
    inaczej collectstatic pod settings.production nie wystartuje."""
    from pathlib import Path

    dockerfile = (
        Path(__file__).resolve().parents[3] / "docker" / "bpp_base" / "Dockerfile"
    )
    if not dockerfile.exists():
        pytest.skip("Dockerfile niedostępny w tym środowisku")
    tekst = dockerfile.read_text(encoding="utf-8")
    bloki = [
        b
        for b in tekst.split("\nRUN ")
        if b.startswith(f"DJANGO_BPP_SECRET_KEY={SECRET_KEY_BUILD_DUMMY}")
    ]
    assert bloki
    for blok in bloki:
        assert "DJANGO_BPP_BUILD_STAGE=1" in blok.split("collectstatic")[0]
    assert "ENV DJANGO_BPP_BUILD_STAGE" not in tekst
