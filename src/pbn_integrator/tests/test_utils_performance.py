"""
Tests for pbn_integrator performance and data consistency.

For system data tests, see test_utils_system_data.py
For author tests, see test_utils_authors.py
For publication sync tests, see test_utils_publication_sync.py
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
# STRESS TESTS - Large Data Volumes
# ============================================================================


@pytest.mark.django_db
class TestLargeDataVolumes:
    """Test performance with large data volumes"""

    def test_sync_performance_with_many_publications(
        self, pbn_charakter_formalny, pbn_jezyk
    ):
        """Should efficiently handle synchronization of 100+ publications"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        # Create 100 publications
        for i in range(100):
            Wydawnictwo_Zwarte.objects.create(
                tytul_oryginalny=f"Publication {i}",
                isbn=f"isbn_{i:04d}" if i % 2 == 0 else "",
                e_isbn=f"e_isbn_{i:04d}" if i % 3 == 0 else "",
                rok=PBN_MIN_ROK + (i % 10),
                doi=f"10.9999/pub{i:04d}",
                charakter_formalny=pbn_charakter_formalny,
                jezyk=pbn_jezyk,
                **required,
            )

        # Should complete without issues
        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert len(synced) > 0
        assert len(synced) <= 100

    def test_sync_with_mixed_publication_types(self, pbn_charakter_formalny, pbn_jezyk):
        """Should correctly filter mixed publication types"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        # Create 30 continuous publications
        for i in range(30):
            Wydawnictwo_Ciagle.objects.create(
                tytul_oryginalny=f"Journal {i}",
                doi=f"10.{i}" if i % 2 == 0 else "",
                rok=PBN_MIN_ROK + (i % 5),
                charakter_formalny=pbn_charakter_formalny,
                jezyk=pbn_jezyk,
                **required,
            )

        # Create 30 book publications
        for i in range(30):
            Wydawnictwo_Zwarte.objects.create(
                tytul_oryginalny=f"Book {i}",
                isbn=f"isbn_{i}" if i % 2 == 0 else "",
                rok=PBN_MIN_ROK + (i % 5),
                charakter_formalny=pbn_charakter_formalny,
                jezyk=pbn_jezyk,
                **required,
            )

        # Each filter should return only its type
        ciagle_synced = list(wydawnictwa_ciagle_do_synchronizacji())
        zwarte_synced = list(wydawnictwa_zwarte_do_synchronizacji())

        # Ensure no overlap - type filtering is working
        for pub in ciagle_synced:
            assert isinstance(pub, Wydawnictwo_Ciagle)

        for pub in zwarte_synced:
            assert isinstance(pub, Wydawnictwo_Zwarte)


# ============================================================================
# DATA CONSISTENCY TESTS
# ============================================================================


@pytest.mark.django_db
class TestDataConsistency:
    """Test data consistency during synchronization"""

    def test_sync_does_not_modify_publications(self, pbn_charakter_formalny, pbn_jezyk):
        """Synchronization filtering should not modify publication records"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        pub = Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="Original Title",
            isbn="123456",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required,
        )

        original_title = pub.tytul_oryginalny
        original_isbn = pub.isbn

        # Run synchronization filter
        list(wydawnictwa_zwarte_do_synchronizacji())

        # Verify publication is unchanged
        pub.refresh_from_db()
        assert pub.tytul_oryginalny == original_title
        assert pub.isbn == original_isbn

    def test_sync_idempotent_multiple_calls(self, pbn_charakter_formalny, pbn_jezyk):
        """Multiple sync calls should return same results"""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        for i in range(10):
            Wydawnictwo_Zwarte.objects.create(
                tytul_oryginalny=f"Publication {i}",
                isbn=f"isbn_{i}" if i % 2 == 0 else "",
                rok=PBN_MIN_ROK + (i % 5),
                charakter_formalny=pbn_charakter_formalny,
                jezyk=pbn_jezyk,
                **required,
            )

        # Call sync multiple times
        result1 = set(wydawnictwa_zwarte_do_synchronizacji())
        result2 = set(wydawnictwa_zwarte_do_synchronizacji())
        result3 = set(wydawnictwa_zwarte_do_synchronizacji())

        # Results should be identical
        assert result1 == result2
        assert result2 == result3
