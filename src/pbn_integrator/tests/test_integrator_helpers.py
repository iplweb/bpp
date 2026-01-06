"""Tests for helper functions in pbn_integrator.

This module contains tests for:
- assert_dictionary_empty - dictionary validation function
- pbn_keywords_to_slowa_kluczowe - keyword conversion from PBN format

These are unit tests that do not require database access unless explicitly marked.
"""

import pytest

from pbn_integrator.importer import (
    assert_dictionary_empty,
    pbn_keywords_to_slowa_kluczowe,
)


class TestAssertDictionaryEmpty:
    """Test assert_dictionary_empty function for validation."""

    def test_assert_dictionary_empty_with_empty_dict(self):
        """Should not raise exception when dictionary is empty."""
        try:
            assert_dictionary_empty({})
        except AssertionError:
            pytest.fail("assert_dictionary_empty should not raise for empty dict")

    def test_assert_dictionary_empty_with_populated_dict_warns(self, capsys):
        """Should print warning when dictionary is not empty and warn=True."""
        test_dict = {"key": "value", "another": "data"}
        assert_dictionary_empty(test_dict, warn=True)
        # Verify warning was printed
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_assert_dictionary_empty_with_populated_dict_raises(self):
        """Should raise AssertionError when dictionary not empty and warn=False."""
        test_dict = {"key": "value"}
        with pytest.raises(AssertionError):
            assert_dictionary_empty(test_dict, warn=False)

    def test_assert_dictionary_empty_nested_dict(self):
        """Should handle nested dictionaries."""
        nested = {"outer": {"inner": "value"}}
        with pytest.raises(AssertionError):
            assert_dictionary_empty(nested, warn=False)


class TestPbnKeywordsToSlowaKluczowe:
    """Test keyword conversion from PBN to BPP format."""

    def test_keywords_conversion_list_single_item(self):
        """Should return set when list has one element."""
        keywords = {"pol": ["research"]}
        result = pbn_keywords_to_slowa_kluczowe(keywords)
        # Single-item list gets extracted and converted to set
        assert isinstance(result, set)
        assert "research" in result

    def test_keywords_conversion_list_multiple_items(self):
        """Should return set when list has multiple items."""
        keywords = {"pol": ["word1", "word2", "word3"]}
        result = pbn_keywords_to_slowa_kluczowe(keywords)
        assert isinstance(result, set)
        assert "word1" in result
        assert "word2" in result

    def test_keywords_conversion_missing_language(self):
        """Should return empty list for missing language."""
        keywords = {"eng": ["test"]}
        result = pbn_keywords_to_slowa_kluczowe(keywords, lang="pol")
        assert result == []

    def test_keywords_conversion_string_with_comma_separator(self):
        """Should split string by comma."""
        keywords = {"pol": "word1,word2,word3"}
        result = pbn_keywords_to_slowa_kluczowe(keywords)
        assert isinstance(result, set)
        assert len(result) == 3

    def test_keywords_conversion_string_with_semicolon_separator(self):
        """Should split string by semicolon."""
        keywords = {"pol": "word1;word2;word3"}
        result = pbn_keywords_to_slowa_kluczowe(keywords)
        assert isinstance(result, set)

    def test_keywords_conversion_empty_list(self):
        """Should return empty list for empty keywords."""
        keywords = {"pol": []}
        result = pbn_keywords_to_slowa_kluczowe(keywords)
        assert result == []
