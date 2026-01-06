"""
Tests for pbn_integrator publication synchronization.

For system data tests, see test_utils_system_data.py
For author tests, see test_utils_authors.py
For performance tests, see test_utils_performance.py
"""

import pytest
from model_bakery import baker

from bpp.const import PBN_MIN_ROK
from bpp.models import Status_Korekty, Typ_KBN, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_integrator.utils import (
    wydawnictwa_ciagle_do_synchronizacji,
    wydawnictwa_zwarte_do_synchronizacji,
)

# ============================================================================
# INTEGRATION TESTS - Publication Synchronization Details
# ============================================================================


@pytest.mark.django_db
class TestPublicationSyncIntegration:
    """Integration tests for publication synchronization with utils"""

    def test_zwarte_missing_required_isbn_variants(
        self, pbn_charakter_formalny, pbn_jezyk
    ):
        """Should exclude Zwarte publications without ISBN or E-ISBN"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        # Publication with neither ISBN nor E-ISBN should not sync
        no_isbn = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="No ISBN",
            doi="10.1234/test",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert no_isbn not in synced

    def test_zwarte_with_parent_publication_www(
        self, pbn_charakter_formalny, pbn_jezyk
    ):
        """Should sync if parent publication has www"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        parent = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Parent with WWW",
            www="http://example.com",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        child = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Child",
            isbn="123456",
            wydawnictwo_nadrzedne=parent,
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert child in synced

    def test_ciagle_requires_doi_or_www(self, pbn_charakter_formalny, pbn_jezyk):
        """Should require DOI, www, or public_www for continuous publications"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        with_doi = Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="With DOI",
            doi="10.5678/test",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        with_www = Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="With WWW",
            www="http://journal.com",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        without_any = Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="Without Any",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_ciagle_do_synchronizacji())
        assert with_doi in synced
        assert with_www in synced
        assert without_any not in synced


# ============================================================================
# EDGE CASE TESTS - Character Encoding & Data Quality
# ============================================================================


@pytest.mark.django_db
class TestDataQualityEdgeCases:
    """Test edge cases related to data quality and encoding"""

    def test_zwarte_sync_with_special_characters_in_title(
        self, pbn_charakter_formalny, pbn_jezyk
    ):
        """Should handle special characters in publication titles"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        special_title = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Title with special: żółw, łódź, ąęć",
            isbn="123456",
            rok=PBN_MIN_ROK,
            doi="10.9999/special",
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert special_title in synced

    def test_ciagle_with_unicode_characters(self, pbn_charakter_formalny, pbn_jezyk):
        """Should handle Unicode characters in continuous publication data"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        unicode_pub = Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="Журнал методических исследований",  # Russian
            doi="10.9999/unicode",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_ciagle_do_synchronizacji())
        assert unicode_pub in synced

    def test_sync_with_boundary_year(self, pbn_charakter_formalny, pbn_jezyk):
        """Should handle publications at minimum year boundary"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        # Exactly at PBN_MIN_ROK
        at_boundary = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="At Boundary",
            isbn="123456",
            rok=PBN_MIN_ROK,
            doi="10.9999/boundary",
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        # Just before PBN_MIN_ROK
        before_boundary = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Before Boundary",
            isbn="654321",
            rok=PBN_MIN_ROK - 1,
            doi="10.9999/before",
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert at_boundary in synced
        assert before_boundary not in synced
