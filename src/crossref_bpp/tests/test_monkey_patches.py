import gzip
import json
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError

from crossref_bpp.monkey_patches import PatchedWorks


@pytest.fixture
def patched_works():
    """Create a PatchedWorks instance for testing."""
    works = PatchedWorks()
    # Mock the required attributes
    works.ENDPOINT = "works"
    works.custom_header = {}
    works.timeout = 30
    works.do_http_request = Mock()
    return works


@pytest.fixture
def sample_json_data():
    """Sample JSON data for testing."""
    return {"message": {"title": ["Test Article"], "DOI": "10.1234/test.doi"}}


@pytest.fixture
def sample_json_bytes(sample_json_data):
    """Sample JSON data as bytes."""
    return json.dumps(sample_json_data).encode("utf-8")


def test_json_method_with_valid_utf8_content(patched_works, sample_json_bytes):
    """Test json method with valid UTF-8 content."""
    result = patched_works.json(sample_json_bytes, encoding=None)
    expected = {"message": {"title": ["Test Article"], "DOI": "10.1234/test.doi"}}
    assert result == expected


def test_json_method_with_explicit_encoding(patched_works, sample_json_data):
    """Test json method with explicit encoding provided."""
    content = json.dumps(sample_json_data).encode("utf-16")
    result = patched_works.json(content, encoding="utf-16")
    assert result == sample_json_data


def test_json_method_with_utf8_bom(patched_works, sample_json_data):
    """Test json method with UTF-8 BOM detection."""
    content = json.dumps(sample_json_data).encode("utf-8-sig")
    result = patched_works.json(content, encoding=None)
    assert result == sample_json_data


def test_json_method_with_utf16_detection(patched_works, sample_json_data):
    """Test json method with UTF-16 encoding detection."""
    content = json.dumps(sample_json_data).encode("utf-16")
    result = patched_works.json(content, encoding=None)
    assert result == sample_json_data


def test_json_method_with_invalid_json(patched_works):
    """Test json method with invalid JSON content."""
    invalid_json = b'{"invalid": json}'
    # The monkey patch doesn't catch standard json.JSONDecodeError, only RequestsJSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        patched_works.json(invalid_json, encoding=None)


def test_json_method_with_unicode_decode_error(patched_works):
    """Test json method handling UnicodeDecodeError."""
    # Create content that will cause UnicodeDecodeError when trying to decode as UTF-8
    content = b'\xff\xff{"test": "value"}'  # Invalid UTF-8
    # This should fall back to the second try block, but will still raise an error
    with patch("crossref_bpp.monkey_patches.guess_json_utf", return_value="utf-8"):
        # The UnicodeDecodeError is caught, and it falls back to the second try
        # But the content is still invalid, so it will raise UnicodeDecodeError
        with pytest.raises(UnicodeDecodeError):
            patched_works.json(content, encoding=None)


def test_json_method_with_empty_content(patched_works):
    """Test json method with empty content."""
    # Empty content will raise JSONDecodeError, not return None
    with pytest.raises(json.JSONDecodeError):
        patched_works.json(b"", encoding=None)


def test_json_method_with_short_content(patched_works):
    """Test json method with content shorter than 3 bytes."""
    result = patched_works.json(b"{}", encoding=None)
    assert result == {}


@patch("crossref_bpp.monkey_patches.build_url_endpoint")
def test_doi_method_success_with_gzip(mock_build_url, patched_works, sample_json_data):
    """Test doi method with successful gzip response."""
    mock_build_url.return_value = "https://api.crossref.org/works/10.1234/test.doi"

    # Create gzip-compressed JSON response
    json_content = json.dumps(sample_json_data).encode("utf-8")
    gzip_content = gzip.compress(json_content)

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-encoding": "gzip"}
    mock_response.content = gzip_content
    mock_response.encoding = "utf-8"

    patched_works.do_http_request.return_value = mock_response

    result = patched_works.doi("10.1234/test.doi")

    assert result == sample_json_data["message"]
    patched_works.do_http_request.assert_called_once()


@patch("crossref_bpp.monkey_patches.build_url_endpoint")
def test_doi_method_success_without_gzip(
    mock_build_url, patched_works, sample_json_data
):
    """Test doi method with successful non-gzip response."""
    mock_build_url.return_value = "https://api.crossref.org/works/10.1234/test.doi"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.return_value = sample_json_data

    patched_works.do_http_request.return_value = mock_response

    result = patched_works.doi("10.1234/test.doi")

    assert result == sample_json_data["message"]


@patch("crossref_bpp.monkey_patches.build_url_endpoint")
def test_doi_method_not_found(mock_build_url, patched_works):
    """Test doi method with 404 response."""
    mock_build_url.return_value = "https://api.crossref.org/works/10.1234/notfound.doi"

    mock_response = Mock()
    mock_response.status_code = 404

    patched_works.do_http_request.return_value = mock_response

    result = patched_works.doi("10.1234/notfound.doi")

    assert result is None


@patch("crossref_bpp.monkey_patches.build_url_endpoint")
def test_doi_method_with_bad_gzip(mock_build_url, patched_works, sample_json_data):
    """Test doi method with bad gzip content that falls back to regular json."""
    mock_build_url.return_value = "https://api.crossref.org/works/10.1234/test.doi"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-encoding": "gzip"}
    mock_response.content = b"not actually gzip content"
    mock_response.json.return_value = sample_json_data

    patched_works.do_http_request.return_value = mock_response

    result = patched_works.doi("10.1234/test.doi")

    assert result == sample_json_data["message"]
    mock_response.json.assert_called_once()


@patch("crossref_bpp.monkey_patches.build_url_endpoint")
def test_doi_method_only_message_false(mock_build_url, patched_works, sample_json_data):
    """Test doi method with only_message=False."""
    mock_build_url.return_value = "https://api.crossref.org/works/10.1234/test.doi"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.return_value = sample_json_data

    patched_works.do_http_request.return_value = mock_response

    result = patched_works.doi("10.1234/test.doi", only_message=False)

    assert result == sample_json_data


@patch("crossref_bpp.monkey_patches.build_url_endpoint")
def test_doi_method_gzip_only_message_false(
    mock_build_url, patched_works, sample_json_data
):
    """Test doi method with gzip and only_message=False."""
    mock_build_url.return_value = "https://api.crossref.org/works/10.1234/test.doi"

    # Create gzip-compressed JSON response
    json_content = json.dumps(sample_json_data).encode("utf-8")
    gzip_content = gzip.compress(json_content)

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-encoding": "gzip"}
    mock_response.content = gzip_content
    mock_response.encoding = "utf-8"

    patched_works.do_http_request.return_value = mock_response

    result = patched_works.doi("10.1234/test.doi", only_message=False)

    # When only_message=False and gzip, it returns the raw content, not the parsed result
    assert result == json_content


def test_json_method_with_kwargs(patched_works):
    """Test json method passes through kwargs to json.loads."""
    content = b'{"test": 1.5}'

    # Test with parse_float parameter
    result = patched_works.json(content, encoding=None, parse_float=str)
    assert result == {"test": "1.5"}


def test_json_method_raises_requests_json_decode_error(patched_works):
    """Test that json method raises JSONDecodeError for invalid JSON."""
    invalid_json = b'{"key": invalid}'

    # The current implementation doesn't catch json.JSONDecodeError, only RequestsJSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        patched_works.json(invalid_json, encoding=None)


def test_json_method_with_encoding_detection_fallback(patched_works):
    """Test json method when encoding detection fails but content is still parseable."""
    # Create valid JSON that will fail encoding detection but succeed in final parse
    content = json.dumps({"test": "value"}).encode("latin-1")

    with patch("crossref_bpp.monkey_patches.guess_json_utf", return_value=None):
        result = patched_works.json(content, encoding=None)
        # Should fall through to the final json.loads attempt
        assert result == {"test": "value"}


def test_json_method_with_requests_json_decode_error_handling(patched_works):
    """Test that RequestsJSONDecodeError is properly re-raised."""
    content = b'{"valid": "json"}'

    # Mock complexjson.loads to raise RequestsJSONDecodeError in the encoding detection path
    with patch("crossref_bpp.monkey_patches.guess_json_utf", return_value="utf-8"):
        with patch("crossref_bpp.monkey_patches.complexjson.loads") as mock_loads:
            # Create a RequestsJSONDecodeError to test the except block
            original_error = RequestsJSONDecodeError("Test error", "doc", 0)
            mock_loads.side_effect = original_error

            with pytest.raises(RequestsJSONDecodeError) as exc_info:
                patched_works.json(content, encoding=None)

            # Verify the error is re-raised correctly
            assert exc_info.value.msg == "Test error"
            assert exc_info.value.doc == "doc"
            assert exc_info.value.pos == 0


def test_json_method_requests_decode_error_in_fallback(patched_works):
    """Test RequestsJSONDecodeError handling in the fallback path."""
    content = b'{"test": "content"}'

    # Mock to skip the encoding detection and go to fallback
    with patch("crossref_bpp.monkey_patches.guess_json_utf", return_value=None):
        with patch("crossref_bpp.monkey_patches.complexjson.loads") as mock_loads:
            # Create a RequestsJSONDecodeError for the fallback path
            original_error = RequestsJSONDecodeError(
                "Fallback error", "fallback_doc", 5
            )
            mock_loads.side_effect = original_error

            with pytest.raises(RequestsJSONDecodeError) as exc_info:
                patched_works.json(content, encoding=None)

            # Verify the error is re-raised correctly in fallback
            assert exc_info.value.msg == "Fallback error"
            assert exc_info.value.doc == "fallback_doc"
            assert exc_info.value.pos == 5
