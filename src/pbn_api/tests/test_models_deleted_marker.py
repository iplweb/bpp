"""Testy markera „[❌ USUNIĘTY]" w __str__ modeli PBN.

Blokują zachowanie na czas adopcji property ``is_deleted``
z django_pbn_client 0.2 (zamiast magic-stringa ``status == "DELETED"``).
"""

import pytest

from pbn_api.models import (
    Conference,
    Institution,
    Journal,
    Publication,
    Publisher,
    Scientist,
)

MARKER = "[❌ USUNIĘTY]"
MODELS = [Journal, Institution, Publisher, Publication, Scientist, Conference]


@pytest.mark.parametrize("model", MODELS)
def test_str_ma_marker_dla_deleted(model):
    obj = model(status="DELETED", versions=[{"current": True, "object": {}}])
    assert obj.is_deleted
    assert str(obj).startswith(MARKER)


@pytest.mark.parametrize("model", MODELS)
def test_str_bez_markera_dla_active(model):
    obj = model(status="ACTIVE", versions=[{"current": True, "object": {}}])
    assert not obj.is_deleted
    assert MARKER not in str(obj)
