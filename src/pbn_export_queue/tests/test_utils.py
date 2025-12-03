"""Tests for pbn_export_queue utility functions"""

from datetime import datetime
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker

from pbn_export_queue.views import (
    _format_submission_date,
    _get_record_title,
    _get_user_info,
    _parse_error_details,
    parse_pbn_api_error,
)

User = get_user_model()


# ============================================================================
# PARSE_PBN_API_ERROR TESTS
# ============================================================================


def test_parse_pbn_api_error_with_dict_response():
    """Test parsing PBN API error when JSON response is a dictionary"""
    exception_text = (
        "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', "
        '\'{"message": "Validation failed", "description": "Invalid data", '
        '"details": {"field": "value"}}\')'
    )

    result = parse_pbn_api_error(exception_text)

    assert result["is_pbn_api_error"] is True
    assert result["exception_type"] == "HttpException"
    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert result["error_message"] == "Validation failed"
    assert result["error_description"] == "Invalid data"
    assert "field" in result["error_details_json"]


def test_parse_pbn_api_error_with_list_response():
    """Test parsing PBN API error when JSON response is a list"""
    exception_text = (
        "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', "
        '\'[{"error": "First error"}, {"error": "Second error"}]\')'
    )

    result = parse_pbn_api_error(exception_text)

    assert result["is_pbn_api_error"] is True
    assert result["exception_type"] == "HttpException"
    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert result["error_message"] == "PBN API zwróciło listę błędów"
    assert "First error" in result["error_details_json"]
    assert "Second error" in result["error_details_json"]


def test_parse_pbn_api_error_with_empty_list_response():
    """Test parsing PBN API error when JSON response is an empty list"""
    exception_text = (
        "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '[]')"
    )

    result = parse_pbn_api_error(exception_text)

    assert result["is_pbn_api_error"] is True
    assert result["exception_type"] == "HttpException"
    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert result["error_message"] == "PBN API zwróciło listę błędów"
    assert result["error_details_json"] == "[]"


def test_parse_pbn_api_error_with_string_response():
    """Test parsing PBN API error when JSON response is a string (unexpected type)"""
    exception_text = (
        "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', "
        "'\"Just a string\"')"
    )

    result = parse_pbn_api_error(exception_text)

    assert result["is_pbn_api_error"] is True
    assert result["exception_type"] == "HttpException"
    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert result["error_message"] == "Nieoczekiwany typ odpowiedzi PBN API"
    assert "Just a string" in result["error_details_json"]


def test_parse_pbn_api_error_with_number_response():
    """Test parsing PBN API error when JSON response is a number (unexpected type)"""
    exception_text = (
        "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '42')"
    )

    result = parse_pbn_api_error(exception_text)

    assert result["is_pbn_api_error"] is True
    assert result["exception_type"] == "HttpException"
    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert result["error_message"] == "Nieoczekiwany typ odpowiedzi PBN API"
    assert "42" in result["error_details_json"]


def test_parse_pbn_api_error_with_non_pbn_error():
    """Test parsing non-PBN error returns correct result"""
    exception_text = "Some random error message"

    result = parse_pbn_api_error(exception_text)

    assert result["is_pbn_api_error"] is False
    assert result["raw_error"] == "Some random error message"


def test_parse_pbn_api_error_with_none():
    """Test parsing None exception text"""
    result = parse_pbn_api_error(None)

    assert result["is_pbn_api_error"] is False
    assert result["raw_error"] == "Brak szczegółów błędu"


# ============================================================================
# _GET_RECORD_TITLE TESTS
# ============================================================================


@pytest.mark.django_db
def test_get_record_title_with_tytul_oryginalny(wydawnictwo_ciagle):
    """Test _get_record_title extracts tytul_oryginalny"""
    wydawnictwo_ciagle.tytul_oryginalny = "Test Article Title"
    result = _get_record_title(wydawnictwo_ciagle)

    assert result == "Test Article Title"


@pytest.mark.django_db
def test_get_record_title_with_opis_bibliograficzny_cache(wydawnictwo_ciagle):
    """Test _get_record_title falls back to opis_bibliograficzny_cache"""
    wydawnictwo_ciagle.tytul_oryginalny = None
    wydawnictwo_ciagle.opis_bibliograficzny_cache = "Cached description"
    result = _get_record_title(wydawnictwo_ciagle)

    assert result == "Cached description"


def test_get_record_title_with_none():
    """Test _get_record_title with None returns default"""
    result = _get_record_title(None)

    assert result == "Nieznany rekord"


def test_get_record_title_with_empty_fields():
    """Test _get_record_title with empty fields returns default"""
    rekord = Mock()
    rekord.tytul_oryginalny = None
    rekord.opis_bibliograficzny_cache = None

    result = _get_record_title(rekord)

    assert result == "Nieznany rekord"


# ============================================================================
# _PARSE_ERROR_DETAILS TESTS
# ============================================================================


def test_parse_error_details_with_valid_exception():
    """Test _parse_error_details parses valid exception tuple"""
    sent_data = Mock()
    sent_data.exception = (
        '(400, "/api/v1/publications", \'{"message": "Error", "code": 400}\')'
    )
    sent_data.api_response_status = None

    result = _parse_error_details(sent_data)

    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert "Error" in result["error_details"]


def test_parse_error_details_with_no_exception():
    """Test _parse_error_details with no exception"""
    sent_data = Mock()
    sent_data.exception = None
    sent_data.api_response_status = 404

    result = _parse_error_details(sent_data)

    assert result["error_code"] == 404
    assert result["error_endpoint"] == "Nieznany endpoint"
    assert result["error_details"] == "Brak szczegółów błędu"


def test_parse_error_details_with_invalid_exception():
    """Test _parse_error_details with invalid exception format"""
    sent_data = Mock()
    sent_data.exception = "Not a valid tuple"
    sent_data.api_response_status = None

    result = _parse_error_details(sent_data)

    assert result["error_code"] == "Brak kodu błędu"
    assert result["error_details"] == "Not a valid tuple"


# ============================================================================
# _FORMAT_SUBMISSION_DATE TESTS
# ============================================================================


def test_format_submission_date_with_submitted_at():
    """Test _format_submission_date with submitted_at"""
    sent_data = Mock()
    sent_data.submitted_at = datetime(2024, 1, 15, 10, 30, 45)
    sent_data.last_updated_on = None

    result = _format_submission_date(sent_data)

    assert result == "2024-01-15 10:30:45"


def test_format_submission_date_with_last_updated_on():
    """Test _format_submission_date falls back to last_updated_on"""
    sent_data = Mock()
    sent_data.submitted_at = None
    sent_data.last_updated_on = datetime(2024, 1, 16, 14, 20, 30)

    result = _format_submission_date(sent_data)

    assert result == "2024-01-16 14:20:30"


def test_format_submission_date_with_no_dates():
    """Test _format_submission_date with no dates returns default"""
    sent_data = Mock()
    sent_data.submitted_at = None
    sent_data.last_updated_on = None

    result = _format_submission_date(sent_data)

    assert result == "Nieznana data"


# ============================================================================
# _GET_USER_INFO TESTS
# ============================================================================


@pytest.mark.django_db
def test_get_user_info_with_email():
    """Test _get_user_info extracts email and name"""
    user = baker.make(
        User,
        email="test@example.com",
        first_name="John",
        last_name="Doe",
    )

    result = _get_user_info(user)

    assert result["user_email"] == "test@example.com"
    assert result["user_name"] == "John Doe"


@pytest.mark.django_db
def test_get_user_info_without_email():
    """Test _get_user_info falls back to username for email"""
    user = baker.make(
        User,
        username="testuser",
        email="",
        first_name="",
        last_name="",
    )

    result = _get_user_info(user)

    assert result["user_email"] == "testuser"
    assert result["user_name"] == "testuser"
