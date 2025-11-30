"""Cleanup operations for PBN integrator."""

from __future__ import annotations

from bpp.models import (
    Autor,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    Uczelnia,
    Wydawca,
    Zrodlo,
)
from pbn_api.models import (
    Conference,
    Country,
    Discipline,
    DisciplineGroup,
    Institution,
    Journal,
    Language,
    OswiadczenieInstytucji,
    Publication,
    PublikacjaInstytucji,
    Publisher,
    Scientist,
    SentData,
)
from pbn_integrator.utils.constants import MODELE_Z_PBN_UID


def clear_match_publications():
    """Clear PBN UID matches for all publication models."""
    for model in MODELE_Z_PBN_UID:
        print(f"Setting pbn_uid_ids of {model} to null...")
        model.objects.exclude(pbn_uid_id=None).update(pbn_uid_id=None)


def clear_publications():
    """Clear all publication-related data."""
    clear_match_publications()
    for model in [OswiadczenieInstytucji, PublikacjaInstytucji, Publication, SentData]:
        model.objects.all()._raw_delete(MODELE_Z_PBN_UID[0].objects.db)


def clear_all():
    """Clear all PBN integration data."""
    for model in (
        Autor,
        Jednostka,
        Wydawca,
        Jezyk,
        Uczelnia,
        Zrodlo,
        Dyscyplina_Naukowa,
    ):
        print(f"Setting pbn_uid_ids of {model} to null...")
        model.objects.exclude(pbn_uid_id=None).update(pbn_uid_id=None)

    clear_publications()

    for model in (
        Language,
        Country,
        Institution,
        Conference,
        SentData,
        Journal,
        Publisher,
        Scientist,
        Discipline,
        DisciplineGroup,
    ):
        print(f"Deleting all {model}")
        model.objects.all()._raw_delete(model.objects.db)
