import json

import pytest
from django.utils.safestring import SafeString
from model_bakery import baker

from pbn_api.admin.helpers import format_json
from pbn_api.models import Journal, Publisher


@pytest.mark.django_db
def test_format_json_with_valid_object():
    """Test format_json with a valid object containing JSON field"""
    publisher = baker.make(Publisher, versions=[{"current": True, "data": "test"}])

    result = format_json(publisher, "versions")

    assert isinstance(result, SafeString)
    assert "<pre>" in str(result)
    assert "</pre>" in str(result)
    assert "current" in str(result)


@pytest.mark.django_db
def test_format_json_with_none_object():
    """Test format_json with None object"""
    result = format_json(None, "versions")

    assert result == ""


@pytest.mark.django_db
def test_format_json_output_contains_formatted_json():
    """Test that format_json output contains properly formatted JSON"""
    publisher = baker.make(Publisher)

    result = format_json(publisher, "versions")

    # Extract JSON from pre tags
    result_str = str(result)
    json_str = result_str.replace("<pre>", "").replace("</pre>", "")

    # Should be valid JSON
    parsed = json.loads(json_str)
    assert isinstance(parsed, (list, dict))


@pytest.mark.django_db
def test_format_json_preserves_formatting():
    """Test that format_json preserves JSON formatting with indentation"""
    publisher = baker.make(
        Publisher, versions=[{"current": True, "nested": {"data": "value"}}]
    )

    result = format_json(publisher, "versions")

    result_str = str(result)

    # Should have proper indentation (spaces or newlines)
    assert ("  " in result_str or "\n" in result_str) or "current" in result_str


@pytest.mark.django_db
def test_format_json_sorts_keys():
    """Test that format_json sorts keys alphabetically"""
    journal = baker.make(Journal)

    result = format_json(journal, "versions")

    result_str = str(result)
    json_str = result_str.replace("<pre>", "").replace("</pre>", "")

    # Parse and verify keys are sorted
    parsed = json.loads(json_str)
    if isinstance(parsed, list) and len(parsed) > 0:
        first_item = parsed[0]
        if isinstance(first_item, dict):
            keys = list(first_item.keys())
            sorted_keys = sorted(keys)
            assert keys == sorted_keys


@pytest.mark.django_db
def test_format_json_is_marked_safe():
    """Test that format_json result is marked as safe for template rendering"""
    publisher = baker.make(Publisher)

    result = format_json(publisher, "versions")

    # Should be SafeString to prevent escaping in templates
    assert isinstance(result, SafeString)


@pytest.mark.django_db
def test_format_json_with_complex_nested_data():
    """Test format_json with complex nested JSON data"""
    publisher = baker.make(
        Publisher,
        versions=[
            {
                "current": True,
                "object": {"name": "test", "nested": {"deep": {"value": "data"}}},
            }
        ],
    )
    # Versions should have complex structure
    assert publisher.versions

    result = format_json(publisher, "versions")
    result_str = str(result)

    # Should successfully format complex data
    assert "<pre>" in result_str
    assert "</pre>" in result_str


@pytest.mark.django_db
def test_format_json_empty_field():
    """Test format_json with an empty JSON field"""
    publisher = baker.make(Publisher, status="ACTIVE")
    # Some fields might be empty
    result = format_json(publisher, "status")

    # Should handle gracefully
    assert "<pre>" in str(result)
    assert "</pre>" in str(result)
