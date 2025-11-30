"""Utility functions for PBN export queue views."""

import json

from django.utils.text import slugify


def sanitize_filename(text, max_length=100):
    """
    Sanitize text to create safe filename.
    Removes unsafe characters and limits length.
    """
    if not text:
        return "export"

    # Use slugify to create safe filename
    safe_name = slugify(text, allow_unicode=False)

    # Limit length
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]

    return safe_name or "export"


def get_filename_from_record(rekord):
    """Generate filename from publication record."""
    if hasattr(rekord, "slug") and rekord.slug:
        return sanitize_filename(rekord.slug)
    elif hasattr(rekord, "tytul_oryginalny") and rekord.tytul_oryginalny:
        return sanitize_filename(rekord.tytul_oryginalny)
    else:
        return "export"


def _extract_exception_type(exception_text, has_pbn_prefix):
    """Extract exception type and message part from exception text."""
    exception_type = "HttpException"  # Default for tuple format
    message_part = exception_text.strip()

    if has_pbn_prefix and ":" in exception_text:
        parts = exception_text.split(":", 1)
        exception_class = parts[0].strip()
        message_part = parts[1].strip()

        # Extract exception type (e.g., "HttpException", "StatementsMissing")
        if "." in exception_class:
            exception_type = exception_class.split(".")[-1]
        else:
            exception_type = exception_class

    return exception_type, message_part


def _parse_json_error(error_json):
    """Parse JSON error response from PBN API."""
    # Handle both dict and list responses from PBN API
    if isinstance(error_json, dict):
        error_message = error_json.get("message", "")
        error_description = error_json.get("description", "")

        # Format details as pretty JSON
        if "details" in error_json:
            error_details_json = json.dumps(
                error_json["details"], indent=2, ensure_ascii=False
            )
        else:
            # If no details, show the whole error JSON
            error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)

        return error_message, error_description, error_details_json

    elif isinstance(error_json, list):
        # PBN API returned a list instead of dict
        error_message = "PBN API zwróciło listę błędów"
        error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)
        return error_message, None, error_details_json

    else:
        # Unexpected JSON type
        error_message = "Nieoczekiwany typ odpowiedzi PBN API"
        error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)
        return error_message, None, error_details_json


def _parse_error_tuple(message_part, exception_type):
    """Parse error tuple format: (code, endpoint, json_str)."""
    import ast

    try:
        exception_tuple = ast.literal_eval(message_part.strip())
        if not (isinstance(exception_tuple, tuple) and len(exception_tuple) >= 3):
            return None

        error_code = int(exception_tuple[0])
        error_endpoint = exception_tuple[1]
        error_json_str = exception_tuple[2]

        result = {
            "is_pbn_api_error": True,
            "exception_type": exception_type,
            "error_code": error_code,
            "error_endpoint": error_endpoint,
        }

        # Try to parse the JSON error response
        try:
            error_json = json.loads(error_json_str)
            error_message, error_description, error_details_json = _parse_json_error(
                error_json
            )

            result["error_message"] = error_message
            if error_description:
                result["error_description"] = error_description
            result["error_details_json"] = error_details_json

        except (json.JSONDecodeError, TypeError, KeyError):
            # JSON parsing failed, but we still have the code and endpoint
            result["error_details_json"] = error_json_str

        return result

    except (ValueError, SyntaxError):
        return None


def parse_pbn_api_error(exception_text):
    """
    Parse PBN API exception to extract error details.

    Returns dict with:
    - is_pbn_api_error: bool
    - error_code: int (if parsed)
    - error_endpoint: str (if parsed)
    - error_message: str (if parsed)
    - error_description: str (if parsed)
    - error_details_json: str (formatted JSON if parsed)
    - exception_type: str (exception class name)
    - raw_error: str (fallback)
    """
    result = {
        "is_pbn_api_error": False,
        "raw_error": exception_text or "Brak szczegółów błędu",
    }

    if not exception_text:
        return result

    # Check if this looks like a PBN error (either with prefix or just a tuple)
    has_pbn_prefix = "pbn_api.exceptions" in exception_text
    looks_like_tuple = exception_text.strip().startswith("(") and "," in exception_text

    if not has_pbn_prefix and not looks_like_tuple:
        return result

    # Extract exception type and message part
    exception_type, message_part = _extract_exception_type(
        exception_text, has_pbn_prefix
    )

    # Security: limit string length to prevent DoS
    if len(message_part.strip()) > 512:
        if has_pbn_prefix:
            result["is_pbn_api_error"] = True
            result["exception_type"] = exception_type
            result["error_message"] = "Error message too long (>512 chars)"
        return result

    # Try to parse as tuple (HttpException format)
    tuple_result = _parse_error_tuple(message_part, exception_type)
    if tuple_result:
        return tuple_result

    # If not a tuple, it's a simple exception like StatementsMissing (only if has pbn_prefix)
    if has_pbn_prefix:
        result["is_pbn_api_error"] = True
        result["exception_type"] = exception_type
        result["error_message"] = message_part.strip()

    return result


def extract_pbn_error_from_komunikat(komunikat):
    """
    Extract PBN API error from komunikat field (traceback).
    Looks for the last line containing 'pbn_api.exceptions'.

    Returns the exception line or None if not found.
    """
    if not komunikat:
        return None

    lines = komunikat.strip().split("\n")

    # Search from the end for a line with pbn_api.exceptions
    for line in reversed(lines):
        if "pbn_api.exceptions" in line:
            return line.strip()

    return None


def get_record_title(rekord):
    """
    Extract title from a publication record.

    Tries tytul_oryginalny first, then opis_bibliograficzny_cache.
    Returns "Nieznany rekord" if no title is found.
    """
    if not rekord:
        return "Nieznany rekord"

    if hasattr(rekord, "tytul_oryginalny") and rekord.tytul_oryginalny:
        return rekord.tytul_oryginalny
    elif (
        hasattr(rekord, "opis_bibliograficzny_cache")
        and rekord.opis_bibliograficzny_cache
    ):
        return rekord.opis_bibliograficzny_cache

    return "Nieznany rekord"


def parse_error_details(sent_data):
    """
    Parse error details from SentData.

    Returns a dict with:
    - error_code: HTTP error code or fallback
    - error_endpoint: API endpoint where error occurred
    - error_details: Formatted error details (JSON or string)
    """
    import ast

    error_code = "Brak kodu błędu"
    error_endpoint = "Nieznany endpoint"
    error_details = "Brak szczegółów błędu"

    if sent_data.exception:
        try:
            # Try to parse tuple format: (code, endpoint, json_str)
            exception_tuple = ast.literal_eval(sent_data.exception)
            if isinstance(exception_tuple, tuple) and len(exception_tuple) >= 3:
                error_code = exception_tuple[0]
                error_endpoint = exception_tuple[1]
                error_json_str = exception_tuple[2]
                try:
                    error_json = json.loads(error_json_str)
                    error_details = json.dumps(error_json, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    error_details = error_json_str
            else:
                error_details = sent_data.exception
        except (ValueError, SyntaxError):
            # If parsing fails, use the raw exception
            error_details = sent_data.exception

    # Use api_response_status as fallback for error code
    if error_code == "Brak kodu błędu" and sent_data.api_response_status:
        error_code = sent_data.api_response_status

    return {
        "error_code": error_code,
        "error_endpoint": error_endpoint,
        "error_details": error_details,
    }


def format_submission_date(sent_data):
    """
    Format submission date for display.

    Uses submitted_at if available, falls back to last_updated_on,
    then to "Nieznana data".
    """
    if sent_data.submitted_at:
        return sent_data.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
    elif sent_data.last_updated_on:
        return sent_data.last_updated_on.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "Nieznana data"


def get_user_info(user):
    """
    Extract user email and full name from User object.

    Returns a dict with:
    - user_email: User's email or username as fallback
    - user_name: User's full name or username as fallback
    """
    user_email = user.email if user.email else user.username
    user_name = user.get_full_name() or user.username

    return {
        "user_email": user_email,
        "user_name": user_name,
    }
