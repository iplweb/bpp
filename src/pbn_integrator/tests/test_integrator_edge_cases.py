"""Tests for edge cases and performance characteristics in pbn_integrator.

This module contains tests for:
- Edge cases in keyword conversion
- Edge cases in dictionary validation
- Performance characteristics with large datasets
- Stress testing for publication filtering

These tests ensure robustness under unusual or extreme conditions.
"""

import pytest
from model_bakery import baker

from bpp.const import PBN_MIN_ROK
from bpp.models import (
    Status_Korekty,
    Typ_KBN,
    Wydawnictwo_Zwarte,
)
from pbn_integrator.importer import (
    assert_dictionary_empty,
    pbn_keywords_to_slowa_kluczowe,
)
from pbn_integrator.utils import wydawnictwa_zwarte_do_synchronizacji


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_keywords_conversion_with_missing_language(self):
        """Should use default empty list when language is missing."""
        keywords = {}
        result = pbn_keywords_to_slowa_kluczowe(keywords, lang="pol")
        # Should return default empty list
        assert result == []

    def test_keywords_conversion_with_custom_language(self):
        """Should handle custom language codes."""
        keywords = {"xyz": ["test1", "test2"]}
        result = pbn_keywords_to_slowa_kluczowe(keywords, lang="xyz")
        assert isinstance(result, set)

    def test_assert_dict_empty_with_zero_values(self):
        """Should still consider dict non-empty even with 0 values."""
        test_dict = {"key": 0, "another": None}
        with pytest.raises(AssertionError):
            assert_dictionary_empty(test_dict, warn=False)

    def test_assert_dict_empty_with_false_value(self):
        """Should still consider dict non-empty even with False."""
        test_dict = {"key": False}
        with pytest.raises(AssertionError):
            assert_dictionary_empty(test_dict, warn=False)


@pytest.mark.django_db
class TestPerformanceCharacteristics:
    """Test performance characteristics and stress conditions."""

    def test_large_keyword_list_conversion(self):
        """Should handle large number of keywords efficiently."""
        # Create a large keyword dictionary with list format
        keywords = {"pol": [f"keyword_{i}" for i in range(100)]}
        result = pbn_keywords_to_slowa_kluczowe(keywords)
        assert isinstance(result, set)
        # Keywords should be in result
        assert len(result) == 100

    def test_multiple_publication_filtering(self, pbn_charakter_formalny, pbn_jezyk):
        """Should efficiently filter large number of publications."""
        required = {
            "status_korekty": baker.make(Status_Korekty),
            "typ_kbn": baker.make(Typ_KBN),
        }

        # Create 50 publications with various combinations
        for i in range(50):
            Wydawnictwo_Zwarte.objects.create(
                tytul_oryginalny=f"Publication {i}",
                e_isbn=f"isbn_{i}" if i % 3 == 0 else "",
                doi=f"doi_{i}" if i % 5 == 0 else "",
                rok=PBN_MIN_ROK + (i % 5),
                charakter_formalny=pbn_charakter_formalny,
                jezyk=pbn_jezyk,
                **required,
            )

        # Should return filtered list without issues
        synced = list(wydawnictwa_zwarte_do_synchronizacji())
        assert isinstance(synced, list)
        assert len(synced) > 0
        assert len(synced) <= 50
