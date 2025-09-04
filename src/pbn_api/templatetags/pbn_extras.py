import re
from datetime import datetime

from django import template

register = template.Library()


@register.filter
def parse_historia_komunikatow(text):
    """
    Parse historia komunikatów field into a structured format.
    Returns a list of message blocks with date and content.
    """
    if not text:
        return []

    # Pattern to match timestamp lines with separator
    # Format: 2025-09-04 19:40:42.324808+00:00
    timestamp_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\+\d{2}:\d{2})"
    separator_pattern = r"={3,}"

    messages = []
    current_message = None

    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Check if this line contains a timestamp
        timestamp_match = re.match(timestamp_pattern, line)
        if timestamp_match:
            # Save the previous message if exists
            if current_message and current_message["content"]:
                messages.append(current_message)

            # Start a new message
            timestamp_str = timestamp_match.group(1)
            current_message = {
                "timestamp": timestamp_str,
                "datetime": parse_timestamp(timestamp_str),
                "content": [],
                "type": "info",  # Default type
            }

            # Skip the separator line if present
            if i + 1 < len(lines) and re.match(separator_pattern, lines[i + 1].strip()):
                i += 1

        elif current_message is not None and line:
            # Add content to current message
            current_message["content"].append(line)

            # Determine message type based on content
            if (
                "błąd" in line.lower()
                or "error" in line.lower()
                or "traceback" in line.lower()
            ):
                current_message["type"] = "error"
            elif "pomyślnie" in line.lower() or "success" in line.lower():
                current_message["type"] = "success"
            elif "autoryzacji" in line.lower() or "auth" in line.lower():
                current_message["type"] = "warning"
            elif "ponownie wysłano" in line.lower():
                current_message["type"] = "resend"

        i += 1

    # Don't forget the last message
    if current_message and current_message["content"]:
        messages.append(current_message)

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
    except BaseException:
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
