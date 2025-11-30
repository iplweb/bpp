"""Deferred Django imports for PBN integrator utils."""

from __future__ import annotations

# Import Django-dependent modules only when Django is ready
try:
    from django.apps import apps

    if apps.ready:
        from import_common.core import matchuj_autora, matchuj_wydawce
        from import_common.normalization import (
            normalize_doi,
            normalize_isbn,
            normalize_tytul_publikacji,
        )
    else:
        # Defer imports until Django is ready
        matchuj_autora = None
        matchuj_wydawce = None
        normalize_doi = None
        normalize_isbn = None
        normalize_tytul_publikacji = None
except Exception:  # noqa
    # Django not available or not configured
    matchuj_autora = None
    matchuj_wydawce = None
    normalize_doi = None
    normalize_isbn = None
    normalize_tytul_publikacji = None


def _ensure_django_imports():
    """Ensure Django-dependent imports are available"""
    global \
        matchuj_autora, \
        matchuj_wydawce, \
        normalize_doi, \
        normalize_isbn, \
        normalize_tytul_publikacji

    if matchuj_autora is None:
        from import_common.core import matchuj_autora as _matchuj_autora
        from import_common.core import matchuj_wydawce as _matchuj_wydawce
        from import_common.normalization import normalize_doi as _normalize_doi
        from import_common.normalization import normalize_isbn as _normalize_isbn
        from import_common.normalization import (
            normalize_tytul_publikacji as _normalize_tytul_publikacji,
        )

        matchuj_autora = _matchuj_autora
        matchuj_wydawce = _matchuj_wydawce
        normalize_doi = _normalize_doi
        normalize_isbn = _normalize_isbn
        normalize_tytul_publikacji = _normalize_tytul_publikacji
