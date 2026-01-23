import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="format_json")
def format_json(value):
    """Format a dict/JSON object as pretty-printed JSON string."""
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            # If already a string, try to parse and re-format
            value = json.loads(value)
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


@register.filter(name="last_line")
def last_line(value):
    """Return the last non-empty line from a multi-line string."""
    if not value:
        return ""
    lines = [line.strip() for line in value.strip().split("\n") if line.strip()]
    return lines[-1] if lines else ""


def _extract_exception_line(value: str) -> str | None:
    """Extract the last line containing pbn_api.exceptions from traceback."""
    lines = [line for line in value.strip().split("\n") if line.strip()]
    for line in reversed(lines):
        if "pbn_api.exceptions" in line:
            return line.strip()
    return None


def _get_fallback_line(value: str) -> str:
    """Get the last non-empty line from value."""
    lines = [line for line in value.strip().split("\n") if line.strip()]
    return lines[-1] if lines else ""


def _parse_exception_parts(exception_line: str) -> tuple[str, str] | None:
    """Parse exception line into (exception_type, message_part)."""
    if ":" not in exception_line:
        return None

    parts = exception_line.split(":", 1)
    exception_class = parts[0].strip()
    message_part = parts[1].strip()

    if "." in exception_class:
        exception_type = exception_class.split(".")[-1]
    else:
        exception_type = exception_class

    return exception_type, message_part


def _format_error_list(
    exception_type: str,
    error_code: str,
    endpoint: str,
    errors: list,
    rodzaj_bledu: str | None = None,
) -> str:
    """Format a list of PBN errors into HTML."""
    html_parts = []

    # For MERYTORYCZNY errors, skip redundant header
    if rodzaj_bledu != "MERYT":
        html_parts.append(
            f'<div class="pbn-error-header">{exception_type}: HTTP {error_code}</div>'
        )

    for error_item in errors:
        if isinstance(error_item, dict):
            error_code_pbn = error_item.get("code", "")
            error_desc = error_item.get("description", "")

            if error_code_pbn:
                html_parts.append(
                    f'<div class="pbn-error-detail">'
                    f"<strong>Kod błędu:</strong> {error_code_pbn}</div>"
                )
            if error_desc:
                html_parts.append(
                    f'<div class="pbn-error-detail">'
                    f"<strong>Opis:</strong> {error_desc}</div>"
                )

    html_parts.append(
        f'<div class="pbn-error-endpoint"><em>Endpoint: {endpoint}</em></div>'
    )
    return "\n".join(html_parts)


def _format_details(details) -> list[str]:
    """Format error details into HTML parts."""
    html_parts = []
    if isinstance(details, dict):
        html_parts.append(
            '<div class="pbn-error-detail"><strong>Szczegóły:</strong></div>'
        )
        for key, val in details.items():
            val_str = (
                ", ".join(str(v) for v in val) if isinstance(val, list) else str(val)
            )
            html_parts.append(
                f'<div class="pbn-error-detail-item">• <em>{key}:</em> {val_str}</div>'
            )
    else:
        html_parts.append(
            f'<div class="pbn-error-detail"><strong>Szczegóły:</strong> {details}</div>'
        )
    return html_parts


def _format_error_object(
    exception_type: str,
    error_code: str,
    endpoint: str,
    error: dict,
    rodzaj_bledu: str | None = None,
) -> str:
    """Format a single error object into HTML."""
    html_parts = []

    # For MERYTORYCZNY errors, skip redundant header/message/description
    # and show only the validation details
    if rodzaj_bledu != "MERYT":
        html_parts.append(
            f'<div class="pbn-error-header">{exception_type}: HTTP {error_code}</div>'
        )

        if "message" in error:
            html_parts.append(
                f'<div class="pbn-error-detail"><strong>Wiadomość:</strong> {error["message"]}</div>'
            )

        if "description" in error:
            html_parts.append(
                f'<div class="pbn-error-detail"><strong>Opis:</strong> {error["description"]}</div>'
            )

    # Always show details (this is what users need for MERYTORYCZNY errors)
    if "details" in error:
        html_parts.extend(_format_details(error["details"]))

    # Always show endpoint for technical debugging
    html_parts.append(
        f'<div class="pbn-error-endpoint"><em>Endpoint: {endpoint}</em></div>'
    )
    return "\n".join(html_parts)


def _format_http_exception(
    exception_type: str,
    error_code: str,
    endpoint: str,
    json_str: str,
    rodzaj_bledu: str | None = None,
) -> str | None:
    """Format HTTP exception with JSON payload. Returns None if JSON parsing fails."""
    # Unescape the JSON string
    json_str = json_str.replace('\\"', '"').replace("\\\\", "\\")

    try:
        error_json = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    if isinstance(error_json, list) and error_json:
        return _format_error_list(
            exception_type, error_code, endpoint, error_json, rodzaj_bledu
        )

    return _format_error_object(
        exception_type, error_code, endpoint, error_json, rodzaj_bledu
    )


# Regex pattern for HttpException tuple format
_HTTP_EXCEPTION_PATTERN = re.compile(
    r'\((\d+),\s*["\']([^"\']+)["\']\s*,\s*["\'](.+)["\']\s*\)\s*$',
    re.DOTALL,
)


@register.filter(name="format_pbn_error")
def format_pbn_error(value, rodzaj_bledu=None):
    """
    Format PBN API error in a readable way.
    Extracts the last line with pbn_api.exceptions from traceback and formats it.
    Handles format: pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{"code":400,...}')

    Args:
        value: The error message/traceback string
        rodzaj_bledu: Optional error type ('MERYT' or 'TECH') to control display
    """
    if not value:
        return ""

    exception_line = _extract_exception_line(value)
    if not exception_line:
        return mark_safe(
            f'<div class="pbn-error-text">{_get_fallback_line(value)}</div>'
        )

    try:
        parsed = _parse_exception_parts(exception_line)
        if not parsed:
            return mark_safe(f'<div class="pbn-error-text">{exception_line}</div>')

        exception_type, message_part = parsed

        # Try to match HttpException tuple format
        tuple_match = _HTTP_EXCEPTION_PATTERN.match(message_part)
        if tuple_match:
            error_code, endpoint, json_str = tuple_match.groups()
            result = _format_http_exception(
                exception_type, error_code, endpoint, json_str, rodzaj_bledu
            )
            if result:
                return mark_safe(result)
            # JSON parsing failed, return raw error
            return mark_safe(
                f'<div class="pbn-error-text">{exception_type}: HTTP {error_code} - {json_str}</div>'
            )

        # Simple exception format (e.g., StatementsMissing)
        return mark_safe(
            f'<div class="pbn-error-text">{exception_type}: {message_part}</div>'
        )

    except (ValueError, AttributeError, IndexError):
        pass

    return mark_safe(f'<div class="pbn-error-text">{exception_line}</div>')
