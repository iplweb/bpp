import json

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from pbn_client.error_record import parse

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


# UWAGA bezpieczeństwo: treść błędu pochodzi z PBN (niezaufana) i trafia do
# ``mark_safe``. KAŻDA dynamiczna wartość interpolowana do HTML MUSI przejść
# przez ``escape()`` — inaczej payload w odpowiedzi PBN (np. ``<script>``) daje
# stored-XSS w tabeli/detalu kolejki. Statyczne etykiety i klasy CSS są bezpieczne.
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
            f'<div class="pbn-error-header">'
            f"{escape(exception_type)}: HTTP {escape(error_code)}</div>"
        )

    for error_item in errors:
        if isinstance(error_item, dict):
            error_code_pbn = error_item.get("code", "")
            error_desc = error_item.get("description", "")

            if error_code_pbn:
                html_parts.append(
                    f'<div class="pbn-error-detail">'
                    f"<strong>Kod błędu:</strong> {escape(error_code_pbn)}</div>"
                )
            if error_desc:
                html_parts.append(
                    f'<div class="pbn-error-detail">'
                    f"<strong>Opis:</strong> {escape(error_desc)}</div>"
                )

    html_parts.append(
        f'<div class="pbn-error-endpoint"><em>Endpoint: {escape(endpoint)}</em></div>'
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
                f'<div class="pbn-error-detail-item">'
                f"• <em>{escape(key)}:</em> {escape(val_str)}</div>"
            )
    else:
        html_parts.append(
            f'<div class="pbn-error-detail">'
            f"<strong>Szczegóły:</strong> {escape(details)}</div>"
        )
    return html_parts


def _format_error_object(
    exception_type: str,
    error_code: str,
    endpoint: str,
    error,
    rodzaj_bledu: str | None = None,
) -> str:
    """Format a single error payload into HTML.

    ``error`` bywa dict-em (typowo), ale też pustą listą, stringiem albo
    liczbą (zdegenerowany payload PBN). Membership (``"message" in error``)
    jest bezpieczne tylko dla dict-a — dla int-a rzucało ``TypeError``
    (naprawione guardem ``isinstance``). Dla nie-dict-ów pokazujemy sam
    nagłówek + endpoint (jak dla pustej listy/stringa wcześniej).
    """
    html_parts = []

    # For MERYTORYCZNY errors, skip redundant header/message/description
    # and show only the validation details
    if rodzaj_bledu != "MERYT":
        html_parts.append(
            f'<div class="pbn-error-header">'
            f"{escape(exception_type)}: HTTP {escape(error_code)}</div>"
        )

        if isinstance(error, dict) and "message" in error:
            html_parts.append(
                f'<div class="pbn-error-detail">'
                f"<strong>Wiadomość:</strong> {escape(error['message'])}</div>"
            )

        if isinstance(error, dict) and "description" in error:
            html_parts.append(
                f'<div class="pbn-error-detail">'
                f"<strong>Opis:</strong> {escape(error['description'])}</div>"
            )

    # Always show details (this is what users need for MERYTORYCZNY errors)
    if isinstance(error, dict) and "details" in error:
        html_parts.extend(_format_details(error["details"]))

    # Always show endpoint for technical debugging
    html_parts.append(
        f'<div class="pbn-error-endpoint"><em>Endpoint: {escape(endpoint)}</em></div>'
    )
    return "\n".join(html_parts)


def _render_http_error(rec, rodzaj_bledu: str | None) -> str | None:
    """Zrenderuj HTML dla błędu HTTP z ``ErrorRecord``. ``None`` gdy body PBN
    nie jest poprawnym JSON-em (caller pokazuje wtedy surowy tekst)."""
    content_json = rec.content_json
    if content_json is None:
        return None
    error_code = str(rec.status_code)
    if isinstance(content_json, list) and content_json:
        return _format_error_list(
            rec.exception_type, error_code, rec.url, content_json, rodzaj_bledu
        )
    return _format_error_object(
        rec.exception_type, error_code, rec.url, content_json, rodzaj_bledu
    )


@register.filter(name="format_pbn_error")
def format_pbn_error(value, rodzaj_bledu=None):
    """
    Format PBN API error in a readable way.

    Parsowanie surowego stringa błędu jest scentralizowane w
    ``pbn_client.error_record.parse`` (rozpoznaje legacy tuple-repr, traceback z
    prefiksem ``pbn_api``/``pbn_client`` oraz nowy format v1). Ta funkcja jest
    już tylko rendererem HTML nad ``ErrorRecord``.

    Args:
        value: The error message/traceback string
        rodzaj_bledu: Optional error type ('MERYT' or 'TECH') to control display
    """
    if not value:
        return ""

    rec = parse(value)

    # Format v1 (reader-first): blob nie ma ``exception_line`` ani surowej
    # krotki, więc renderujemy WPROST ze strukturalnych pól — inaczej
    # pokazalibyśmy surowy JSON zamiast czytelnego błędu.
    if rec.wire == "v1":
        if rec.kind == "http" and rec.status_code is not None:
            rendered = _render_http_error(rec, rodzaj_bledu)
            if rendered is not None:
                return mark_safe(rendered)
        return mark_safe(
            f'<div class="pbn-error-text">'
            f"{escape(rec.message or rec.fallback_line)}</div>"
        )

    # Brak linii wyjątku PBN (goła krotka / plaintext) → surowa ostatnia linia.
    if rec.exception_line is None:
        return mark_safe(
            f'<div class="pbn-error-text">{escape(rec.fallback_line)}</div>'
        )

    # Linia z modułem PBN, ale bez rozpoznanej klasy (brak ``:``).
    if rec.exception_type is None:
        return mark_safe(
            f'<div class="pbn-error-text">{escape(rec.exception_line)}</div>'
        )

    # HTTP tuple-repr → strukturalny HTML.
    if rec.kind == "http" and rec.status_code is not None:
        rendered = _render_http_error(rec, rodzaj_bledu)
        if rendered is not None:
            return mark_safe(rendered)
        # Body nie jest poprawnym JSON-em — pokaż surowo.
        return mark_safe(
            f'<div class="pbn-error-text">'
            f"{escape(rec.exception_type)}: HTTP {escape(str(rec.status_code))} "
            f"- {escape(rec.content or '')}</div>"
        )

    # Prosty wyjątek (np. StatementsMissing).
    return mark_safe(
        f'<div class="pbn-error-text">'
        f"{escape(rec.exception_type)}: {escape(rec.message or '')}</div>"
    )
