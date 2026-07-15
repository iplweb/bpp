"""Utility functions for PBN export queue views.

Parsowanie surowych stringów błędów PBN jest scentralizowane w
``pbn_client.error_record.parse``. Funkcje ``parse_pbn_api_error`` /
``parse_error_details`` / ``extract_pbn_error_from_komunikat`` są już tylko
adapterami mapującymi ``ErrorRecord`` na kształty oczekiwane przez widoki.
"""

import json

from django.utils.text import slugify
from pbn_client.error_record import parse


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


def _summarize_json_error(error_json):
    """Zwróć ``(error_message, error_description, error_details_json)`` z body
    odpowiedzi PBN — reprodukuje semantykę legacy ``_parse_json_error``."""
    if isinstance(error_json, dict):
        error_message = error_json.get("message", "")
        error_description = error_json.get("description", "")
        if "details" in error_json:
            error_details_json = json.dumps(
                error_json["details"], indent=2, ensure_ascii=False
            )
        else:
            error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)
        return error_message, error_description, error_details_json

    if isinstance(error_json, list):
        return (
            "PBN API zwróciło listę błędów",
            None,
            json.dumps(error_json, indent=2, ensure_ascii=False),
        )

    return (
        "Nieoczekiwany typ odpowiedzi PBN API",
        None,
        json.dumps(error_json, indent=2, ensure_ascii=False),
    )


def _render_pbn_dict(rec, exception_type):
    """Zbuduj dict błędu HTTP z ``ErrorRecord`` (kształt jak legacy)."""
    result = {
        "is_pbn_api_error": True,
        "exception_type": exception_type,
        "error_code": rec.status_code,
        "error_endpoint": rec.url,
    }
    if not rec.content_json_valid:
        # Body nie jest poprawnym JSON-em — zachowaj kod/endpoint, surowy body.
        # (``content_json_valid`` odróżnia to od poprawnego JSON ``null``, który
        # legacy renderował jako „Nieoczekiwany typ odpowiedzi PBN API".)
        result["error_details_json"] = rec.content
        return result

    error_message, error_description, error_details_json = _summarize_json_error(
        rec.content_json
    )
    result["error_message"] = error_message
    if error_description:
        result["error_description"] = error_description
    result["error_details_json"] = error_details_json
    return result


def _message_part(rec, exception_text):
    """Część-komunikat po prefiksie ``moduł.Klasa:`` (lub całość dla gołej
    krotki) — do legacy guardu długości (>512)."""
    if rec.exception_line is not None and ":" in rec.exception_line:
        return rec.exception_line.split(":", 1)[1].strip()
    return exception_text.strip()


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

    rec = parse(exception_text)

    # Format v1 (reader-first): rekord jest już strukturalny; NIE stosujemy
    # legacy guardu >512 (mierzyłby cały blob v1 i błędnie uznał go za „nie-PBN
    # error", psując odczyt v1). Content v1 jest przycięty przy serializacji.
    if rec.wire == "v1":
        if rec.kind == "http" and rec.status_code is not None:
            return _render_pbn_dict(rec, rec.exception_type or "HttpException")
        if rec.is_pbn_api_error:
            result["is_pbn_api_error"] = True
            result["exception_type"] = rec.exception_type or "HttpException"
            result["error_message"] = rec.message or ""
        return result

    has_pbn_prefix = rec.exception_line is not None
    is_tuple_http = rec.kind == "http" and rec.status_code is not None

    # Ani prefiks PBN, ani goła krotka HTTP → to nie jest błąd PBN.
    if not has_pbn_prefix and not is_tuple_http:
        return result

    exception_type = rec.exception_type or "HttpException"

    # Security: limit string length to prevent DoS (jak w legacy).
    if len(_message_part(rec, exception_text)) > 512:
        if has_pbn_prefix:
            result["is_pbn_api_error"] = True
            result["exception_type"] = exception_type
            result["error_message"] = "Error message too long (>512 chars)"
        return result

    if is_tuple_http:
        return _render_pbn_dict(rec, exception_type)

    # Prosty wyjątek z prefiksem PBN, bez krotki HTTP (np. StatementsMissing).
    result["is_pbn_api_error"] = True
    result["exception_type"] = exception_type
    result["error_message"] = (rec.message or "").strip()
    return result


def extract_pbn_error_from_komunikat(komunikat):
    """
    Extract PBN API error from komunikat field (traceback).
    Looks for the last line containing a legacy or extracted PBN exception.

    Returns the exception line or None if not found.
    """
    if not komunikat:
        return None
    rec = parse(komunikat)
    # Blob v1 nie ma „linii wyjątku"; zwracamy cały blob, żeby downstream
    # ``parse_pbn_api_error`` (znający v1) mógł go zinterpretować (reader-first).
    if rec.wire == "v1":
        return komunikat
    return rec.exception_line


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
    error_code = "Brak kodu błędu"
    error_endpoint = "Nieznany endpoint"
    error_details = "Brak szczegółów błędu"

    if sent_data.exception:
        rec = parse(sent_data.exception)
        # Realistyczny ``SentData.exception`` to goła krotka HTTP (``str(e)``),
        # bez prefiksu ``moduł.Klasa:``. Tylko wtedy wyłuskujemy kod/endpoint.
        # Goła krotka HTTP (legacy ``str(e)``) LUB blob v1 — oba mają
        # ``exception_line is None``. Prefiksowane linie (traceback) idą do
        # surowego fallbacku, jak w legacy.
        if (
            rec.kind == "http"
            and rec.status_code is not None
            and rec.exception_line is None
        ):
            error_code = rec.status_code
            error_endpoint = rec.url
            if rec.content_json_valid:
                error_details = json.dumps(
                    rec.content_json, indent=2, ensure_ascii=False
                )
            else:
                error_details = rec.content
        else:
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
