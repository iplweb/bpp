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


@register.filter(name="format_pbn_error")
def format_pbn_error(value):
    """
    Format PBN API error in a readable way.
    Extracts the last line with pbn_api.exceptions from traceback and formats it.
    Handles format: pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{"code":400,...}')
    """
    if not value:
        return ""

    # Extract the last line containing pbn_api.exceptions (this is the actual error)
    # This removes all the traceback stack and keeps only the exception line
    lines = [line for line in value.strip().split("\n") if line.strip()]
    exception_line = None

    # Search from the end for a line with pbn_api.exceptions
    for line in reversed(lines):
        if "pbn_api.exceptions" in line:
            exception_line = line.strip()
            break

    # If no pbn_api.exceptions found, return last line
    if not exception_line:
        return mark_safe(
            f'<div style="font-family: monospace; line-height: 1.5; font-size: 1.05em;">'
            f'{lines[-1] if lines else ""}</div>'
        )

    # Now parse the exception line
    try:
        # Try to extract tuple from HttpException format
        # Format: "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{...}')"
        if ":" in exception_line:
            parts = exception_line.split(":", 1)
            exception_class = parts[0].strip()
            message_part = parts[1].strip()

            # Extract exception type (e.g., "HttpException", "StatementsMissing")
            if "." in exception_class:
                exception_type = exception_class.split(".")[-1]
            else:
                exception_type = exception_class

            # Try to parse as tuple (HttpException format)
            # Format: (400, '/api/v1/publications', '{"code":400,...}')
            tuple_match = re.match(
                r'\((\d+),\s*["\']([^"\']+)["\']\s*,\s*["\'](.+)["\']\s*\)\s*$',
                message_part,
                re.DOTALL,
            )

            if tuple_match:
                error_code = tuple_match.group(1)
                error_endpoint = tuple_match.group(2)
                error_json_str = tuple_match.group(3)

                # Unescape the JSON string
                error_json_str = error_json_str.replace('\\"', '"').replace(
                    "\\\\", "\\"
                )

                # Try to parse the JSON error response
                try:
                    error_json = json.loads(error_json_str)

                    # Build a formatted HTML error message with monospace font
                    html_parts = []
                    html_parts.append(
                        '<div style="font-family: monospace; color: #c00; font-weight: bold; font-size: 1.2em;">'
                        f"{exception_type}: HTTP {error_code}</div>"
                    )

                    if "message" in error_json:
                        html_parts.append(
                            '<div style="font-family: monospace; margin-top: 8px; line-height: 1.5; font-size: 1.05em;">'
                            f'<strong>Wiadomość:</strong> {error_json["message"]}</div>'
                        )

                    if "description" in error_json:
                        html_parts.append(
                            '<div style="font-family: monospace; margin-top: 8px; line-height: 1.5; font-size: 1.05em;">'
                            f'<strong>Opis:</strong> {error_json["description"]}</div>'
                        )

                    if "details" in error_json:
                        details = error_json["details"]
                        if isinstance(details, dict):
                            html_parts.append(
                                '<div style="font-family: monospace; margin-top: 8px; line-height: 1.5; font-size: 1.05em;">'
                                "<strong>Szczegóły:</strong></div>"
                            )
                            for key, val in details.items():
                                if isinstance(val, list):
                                    val_str = ", ".join(str(v) for v in val)
                                else:
                                    val_str = str(val)
                                html_parts.append(
                                    '<div style="font-family: monospace; margin-left: 20px; line-height: 1.5; '
                                    f'font-size: 1.05em;">• <em>{key}:</em> {val_str}</div>'
                                )
                        else:
                            html_parts.append(
                                '<div style="font-family: monospace; margin-top: 8px; line-height: 1.5; font-size: 1.05em;">'
                                f"<strong>Szczegóły:</strong> {details}</div>"
                            )

                    html_parts.append(
                        '<div style="font-family: monospace; margin-top: 12px; font-size: 1em; '
                        f'color: #666; line-height: 1.5;"><em>Endpoint: {error_endpoint}</em></div>'
                    )

                    return mark_safe("\n".join(html_parts))

                except (json.JSONDecodeError, TypeError, KeyError):
                    # JSON parsing failed, return raw error JSON in monospace
                    return mark_safe(
                        f'<div style="font-family: monospace; line-height: 1.5; font-size: 1.05em;">'
                        f"{exception_type}: HTTP {error_code} - {error_json_str}</div>"
                    )

            # If not a tuple format, it's a simple exception like StatementsMissing
            return mark_safe(
                f'<div style="font-family: monospace; line-height: 1.5; font-size: 1.05em;">'
                f"{exception_type}: {message_part.strip()}</div>"
            )

    except (ValueError, AttributeError, IndexError):
        # Parsing failed, return the exception line as-is
        pass

    # Fallback: return exception line in monospace
    return mark_safe(
        f'<div style="font-family: monospace; line-height: 1.5; font-size: 1.05em;">{exception_line}</div>'
    )
