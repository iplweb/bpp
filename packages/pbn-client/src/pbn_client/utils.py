"""Utility functions for PBN API client."""


def mask_secret(value, widocznych=4):
    """Zamaskuj sekret, zostawiając tylko ostatnie ``widocznych`` znaków.

    Do bezpiecznego wypisania tokenów w trybie verbose — sam ogon pozwala
    zidentyfikować token bez ujawniania go w terminalu/CI/logach (uwaga #4).
    """
    if not value:
        return "(brak)"
    s = str(value)
    if len(s) <= widocznych:
        return "*" * len(s)
    return "*" * (len(s) - widocznych) + s[-widocznych:]


def smart_content(content):
    """Decode content to string, handling encoding errors gracefully."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content
