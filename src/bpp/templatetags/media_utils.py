from django import template
from django.core.files.storage import default_storage

register = template.Library()


@register.filter
def media_exists(path):
    """Check if a media file exists in the storage."""
    if not path:
        return False
    return default_storage.exists(path)
