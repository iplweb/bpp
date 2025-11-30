"""Utility functions for PBN API client."""


def smart_content(content):
    """Decode content to string, handling encoding errors gracefully."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content
