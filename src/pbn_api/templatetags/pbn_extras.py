import logging
import re
from datetime import datetime

from django import template

from bpp.util import zaloguj_polkniety_wyjatek

register = template.Library()

logger = logging.getLogger(__name__)


# Format: 2025-09-04 19:40:42.324808+00:00
_TIMESTAMP_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\+\d{2}:\d{2})"
_SEPARATOR_PATTERN = r"={3,}"

# Reguły klasyfikacji typu wiadomości — pierwsza pasująca (kolejność jak
# w pierwotnym łańcuchu if/elif). Zachowane semantyki: w obrębie linii
# wygrywa pierwsza reguła, a kolejne linie nadpisują typ wiadomości.
_TYPE_RULES = (
    (("błąd", "error", "traceback"), "error"),
    (("pomyślnie", "success"), "success"),
    (("autoryzacji", "auth"), "warning"),
    (("ponownie wysłano",), "resend"),
)


def _classify_line(line):
    """Zwróć typ wiadomości dla danej linii albo None, gdy nic nie pasuje."""
    low = line.lower()
    for keywords, msg_type in _TYPE_RULES:
        if any(keyword in low for keyword in keywords):
            return msg_type
    return None


def _new_message(timestamp_str):
    return {
        "timestamp": timestamp_str,
        "datetime": parse_timestamp(timestamp_str),
        "content": [],
        "type": "info",  # Default type
    }


def _split_into_messages(text):
    """Podziel surowy tekst na listę bloków-wiadomości (z surową treścią)."""
    messages = []
    current_message = None
    lines = text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        timestamp_match = re.match(_TIMESTAMP_PATTERN, line)

        if timestamp_match:
            if current_message and current_message["content"]:
                messages.append(current_message)
            current_message = _new_message(timestamp_match.group(1))
            # Skip the separator line if present
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if re.match(_SEPARATOR_PATTERN, next_line):
                i += 1
        elif current_message is not None and line:
            current_message["content"].append(line)
            msg_type = _classify_line(line)
            if msg_type:
                current_message["type"] = msg_type

        i += 1

    if current_message and current_message["content"]:
        messages.append(current_message)
    return messages


@register.filter
def parse_historia_komunikatow(text):
    """
    Parse historia komunikatów field into a structured format.
    Returns a list of message blocks with date and content.
    """
    if not text:
        return []

    messages = _split_into_messages(text)

    # Process content for each message
    for msg in messages:
        msg["content"] = "\n".join(msg["content"]).strip()
        msg["is_traceback"] = "Traceback" in msg["content"]

    # Sort messages by datetime (newest first)
    messages.sort(
        key=lambda x: x["datetime"] if x["datetime"] else datetime.min, reverse=True
    )

    return messages


def parse_timestamp(timestamp_str):
    """Parse timestamp string into datetime object"""
    try:
        # Remove timezone info for simpler parsing
        timestamp_clean = re.sub(r"\+\d{2}:\d{2}$", "", timestamp_str)
        # Remove microseconds if parsing fails
        timestamp_clean = re.sub(r"\.\d+$", "", timestamp_clean)
        return datetime.strptime(timestamp_clean, "%Y-%m-%d %H:%M:%S")
    except Exception:
        zaloguj_polkniety_wyjatek(
            f"Nie udało się sparsować znacznika czasu '{timestamp_str}' "
            "z historii komunikatów PBN",
            logger=logger,
            do_rollbar=True,
        )
        return None


@register.filter
def format_datetime_pl(dt):
    """Format datetime in Polish format"""
    if not dt:
        return ""

    months = {
        1: "stycznia",
        2: "lutego",
        3: "marca",
        4: "kwietnia",
        5: "maja",
        6: "czerwca",
        7: "lipca",
        8: "sierpnia",
        9: "września",
        10: "października",
        11: "listopada",
        12: "grudnia",
    }

    return f"{dt.day} {months.get(dt.month, '')} {dt.year}, {dt.strftime('%H:%M:%S')}"


@register.filter
def message_icon(msg_type):
    """Return appropriate icon class for message type"""
    icons = {
        "error": "fi-x-circle",
        "success": "fi-check-circle",
        "warning": "fi-alert",
        "resend": "fi-refresh",
        "info": "fi-info",
    }
    return icons.get(msg_type, "fi-info")


@register.filter
def message_color(msg_type):
    """Return appropriate color class for message type"""
    colors = {
        "error": "#dc3545",
        "success": "#28a745",
        "warning": "#ffc107",
        "resend": "#17a2b8",
        "info": "#6c757d",
    }
    return colors.get(msg_type, "#6c757d")


@register.filter
def truncate_traceback(content, lines=10):
    """Truncate long traceback to first N lines"""
    if not content or "Traceback" not in content:
        return content

    content_lines = content.split("\n")
    if len(content_lines) <= lines:
        return content

    return (
        "\n".join(content_lines[:lines])
        + f"\n... (obcięto {len(content_lines) - lines} linii)"
    )
