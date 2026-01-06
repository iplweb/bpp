"""Tests for publication synchronization logic.

This module contains tests for:
- wydawnictwa_zwarte_do_synchronizacji (monograph synchronization)
- wydawnictwa_ciagle_do_synchronizacji (continuous publication synchronization)
- Integration tests for publication filtering criteria

Tests verify that publications meet all required criteria for PBN synchronization,
including proper character type, language, year, and identifier requirements.
"""

import pytest
from model_bakery import baker

from bpp.const import PBN_MIN_ROK
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from pbn_integrator.utils import (
    wydawnictwa_ciagle_do_synchronizacji,
    wydawnictwa_zwarte_do_synchronizacji,
)


@pytest.mark.django_db
def test_wydawnictwa_zwarte_do_synchronizacji(pbn_charakter_formalny, pbn_jezyk):
    """Test monograph synchronization filtering.

    Verifies that publications are correctly filtered based on:
    - Valid ISBN or E-ISBN
    - Valid DOI, WWW, or Public WWW (directly or via parent)
    - Valid PBN character type mapping
    - Valid PBN language mapping
    - Year >= PBN_MIN_ROK
    """
    wejda = []
    nie_wejda = []

    required = {
        "status_korekty": baker.make(Status_Korekty),
        "typ_kbn": baker.make(Typ_KBN),
    }

    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="A",
            e_isbn="jest",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="B",
            isbn="jest",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nadrzedne_www = Wydawnictwo_Zwarte.objects.create(
        tytul_oryginalny="C",
        rok=PBN_MIN_ROK,
        www="jest",
        charakter_formalny=pbn_charakter_formalny,
        jezyk=pbn_jezyk,
        **required,
    )
    nadrzedne_public_www = Wydawnictwo_Zwarte.objects.create(
        rok=PBN_MIN_ROK,
        www="jest",
        charakter_formalny=pbn_charakter_formalny,
        jezyk=pbn_jezyk,
        **required,
    )

    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="D",
            isbn="jest",
            rok=PBN_MIN_ROK,
            wydawnictwo_nadrzedne=nadrzedne_www,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )
    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="E",
            isbn="jest",
            rok=PBN_MIN_ROK,
            wydawnictwo_nadrzedne=nadrzedne_public_www,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Charakter formalny bez odpowiednika
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="F",
            doi="jest",
            isbn="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=baker.make(Charakter_Formalny, rodzaj_pbn=None),
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Brak ISBN oraz E-ISBN
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="G",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Brak www oraz public_www oraz DOI
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="H",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            isbn="jest",
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Jezyk bez odpowiednika w PBN
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="I",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            isbn="jest",
            jezyk=baker.make(Jezyk, pbn_uid=None),
            **required,
        )
    )

    nie_wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            # Rok za wczesny
            tytul_oryginalny="J",
            e_isbn="jest",
            doi="jest",
            rok=PBN_MIN_ROK - 10,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    res = list(wydawnictwa_zwarte_do_synchronizacji())
    for elem in wejda:
        assert elem in res, elem.tytul_oryginalny
    for elem in nie_wejda:
        assert elem not in res, elem.tytul_oryginalny


@pytest.mark.django_db
def test_wydawnictwa_ciagle_do_synchronizacji(pbn_charakter_formalny, pbn_jezyk):
    """Test continuous publication synchronization filtering.

    Verifies that publications are correctly filtered based on:
    - Valid DOI, WWW, or Public WWW
    - Valid PBN character type mapping
    - Valid PBN language mapping
    - Year >= PBN_MIN_ROK
    """
    wejda = []
    nie_wejda = []

    required = {
        "status_korekty": baker.make(Status_Korekty),
        "typ_kbn": baker.make(Typ_KBN),
    }

    wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="A",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="B",
            www="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )
    wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="B",
            public_www="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Charakter formalny bez odpowiednika
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="F",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=baker.make(Charakter_Formalny, rodzaj_pbn=None),
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Brak www oraz public_www oraz DOI
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="H",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    nie_wejda.append(
        # Jezyk bez odpowiednika w PBN
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="I",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            doi="jest",
            jezyk=baker.make(Jezyk, pbn_uid=None),
            **required,
        )
    )

    nie_wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            # Rok za wczesny
            tytul_oryginalny="J",
            rok=PBN_MIN_ROK - 10,
            doi="jest",
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )
    )

    res = list(wydawnictwa_ciagle_do_synchronizacji())
    for elem in wejda:
        assert elem in res, elem.tytul_oryginalny
    for elem in nie_wejda:
        assert elem not in res, elem.tytul_oryginalny


@pytest.mark.django_db
class TestPublicationSynchronization:
    """Integration tests for publication synchronization logic."""

    def test_sync_filters_apply_all_criteria(self, pbn_charakter_formalny, pbn_jezyk):
        """Should apply all filter criteria when synchronizing."""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        # Create publications with various combinations
        zwarte_sync = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Should Sync",
            e_isbn="123456",
            rok=PBN_MIN_ROK + 1,
            doi="10.9999/sync",
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        zwarte_no_sync = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Should Not Sync",
            rok=PBN_MIN_ROK + 1,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert zwarte_sync in synced
        assert zwarte_no_sync not in synced

    def test_sync_continuous_with_doi(self, pbn_charakter_formalny, pbn_jezyk):
        """Should include continuous publications with DOI."""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        ciagle = Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="Article with DOI",
            doi="10.1234/test",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_ciagle_do_synchronizacji())
        assert ciagle in synced

    def test_sync_continuous_without_required_fields(
        self, pbn_charakter_formalny, pbn_jezyk
    ):
        """Should exclude continuous publications without required fields."""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        ciagle = Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="No Required Fields",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_ciagle_do_synchronizacji())
        assert ciagle not in synced
