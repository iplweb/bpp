"""Wspólne mapowanie wyjątków DjangoQL na payload JSON z lokalizacją błędu.

Trzon dzielony przez web-owy edytor „Szukaj zapytaniem" (``bpp.views.zapytanie``)
i API DjangoQL (``api_v1.viewsets.zapytanie``). Most między wyjątkami Pythona a
czerwoną falką nakładki ``highlight.js`` (idiom z ``djangoql/example_project``).
"""

import re

from django.core.exceptions import ValidationError


def format_error_text(exc):
    """Czytelny komunikat błędu zapytania (łączy komunikaty ValidationError)."""
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)
    return str(exc)


def locate_token(query, needle):
    """1-based ``(line, column)`` wystąpienia ``needle`` w ``query`` albo None."""
    match = re.search(r"(?<![\w.])" + re.escape(needle) + r"(?![\w])", query)
    pos = match.start() if match else query.find(needle)
    if pos < 0:
        return None
    line = query.count("\n", 0, pos) + 1
    column = pos - query.rfind("\n", 0, pos)
    return line, column


def error_location(exc, query):
    """``(line, column, mark)`` wskazujące miejsce błędu, albo ``(None,)*3``."""
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if line and column:
        return line, column, "to_end"
    value = getattr(exc, "value", None)
    if value:
        loc = locate_token(query, str(value))
        if loc:
            return loc[0], loc[1], "token"
    return None, None, None


def error_payload(exc, query):
    """Słownik odpowiedzi JSON błędu: ``{error[, line, column, mark]}``."""
    payload = {"error": format_error_text(exc)}
    line, column, mark = error_location(exc, query)
    if line and column:
        payload.update(line=line, column=column, mark=mark)
    return payload
