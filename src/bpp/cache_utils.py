"""Utilities for site-aware cache key generation in multi-hosted mode."""


def site_cache_key(key, site_id=None):
    """Prefix a cache key with the site ID to prevent cross-tenant pollution.

    Args:
        key: The base cache key.
        site_id: The Site.pk to use. If None, uses 0 (no site context).

    Returns:
        A cache key prefixed with the site ID.
    """
    if site_id is None:
        site_id = 0
    return f"site_{site_id}:{key}"
