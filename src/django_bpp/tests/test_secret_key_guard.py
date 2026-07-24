"""Testy predykatu fail-closed guard SECRET_KEY (#4 z security review)."""

import pytest

from django_bpp.settings.secret_key_guard import (
    SECRET_KEY_BUILD_DUMMY,
    secret_key_niebezpieczny_placeholder,
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
        # Wartości bezpieczne — produkcja/build wstaje normalnie.
        (SECRET_KEY_BUILD_DUMMY, False),
        ("k9$2mZ!q7wR4tY6uI8oP1aS3dF5gH0jL2xC4vB6nM8", False),
    ],
)
def test_wykrywanie_placeholdera_secret_key(key, oczekiwane):
    assert (
        secret_key_niebezpieczny_placeholder(key, unset_sentinel=SENTINEL) is oczekiwane
    )


def test_wartosc_buildowa_nie_jest_flagowana_nawet_gdyby_zawierala_zmien():
    """Wartość build-owa jest whitelisowana bezwarunkowo — sanity guard, żeby
    nikt nie 'poprawił' predykatu tak, że wywali collectstatic w buildzie."""
    assert (
        secret_key_niebezpieczny_placeholder(
            SECRET_KEY_BUILD_DUMMY, unset_sentinel=SENTINEL
        )
        is False
    )
