"""Constants used throughout the PBN integrator utils module."""

from __future__ import annotations

from bpp.models import (
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

# CPU configuration for multiprocessing
CPU_COUNT = "auto"  # noqa

# Default multiprocessing context
DEFAULT_CONTEXT = "spawn"

# Models that have PBN UID field
MODELE_Z_PBN_UID = (
    Wydawnictwo_Zwarte,
    Wydawnictwo_Ciagle,
    Praca_Doktorska,
    Praca_Habilitacyjna,
)

# PBN error messages
PBN_KOMUNIKAT_ISBN_ISTNIEJE = "Publikacja o identycznym ISBN lub ISMN już istnieje"
PBN_KOMUNIKAT_DOI_ISTNIEJE = "Publikacja o identycznym DOI i typie już istnieje"
