"""Reader-first (P4 Stage 1): adaptery display MUSZĄ rozumieć format v1.

To pinuje naprawę findingów recenzji Fable: przed poprawką ``parse_pbn_api_error``
klasyfikował blob v1 >512 znaków jako „nie-PBN-error", a ``format_pbn_error``
renderował surowy JSON zamiast strukturalnego HTML — czyli Stage 1 NIE kupował
ochrony przed deploy-race, dla której istnieje. Writery nie są jeszcze zmieniane
(Stage 2), ale readery muszą być gotowe na blob v1 JUŻ TERAZ.
"""

import pytest
from django.contrib import admin
from pbn_client.error_record import parse, serialize

from pbn_api.admin.sentdata import SentDataAdmin
from pbn_api.models import SentData
from pbn_export_queue.templatetags.pbn_queue_extras import format_pbn_error
from pbn_export_queue.views.utils import (
    extract_pbn_error_from_komunikat,
    parse_error_details,
    parse_pbn_api_error,
)

# Blob v1 zbudowany tak, jak zapisze go writer w Stage 2 (serialize()). Ma
# >512 znaków dzięki details — dokładnie przypadek, na którym stary reader padał.
_LEGACY = (
    "pbn_api.exceptions.PBNValidationError: (400, '/api/v1/publications', "
    '\'{"code":400,"message":"Bad Request","description":"Validation failed.",'
    '"details":{"isbn":"Publikacja o identycznym ISBN już istnieje! '
    + "x" * 600
    + "\"}}')"
)
V1_BLOB = serialize(parse(_LEGACY))


class _FakeSent:
    def __init__(self, exception, api_response_status=None, pk=1):
        self.exception = exception
        self.api_response_status = api_response_status
        self.pk = pk


def test_v1_blob_is_actually_v1_and_long():
    rec = parse(V1_BLOB)
    assert rec.wire == "v1"
    assert len(V1_BLOB) > 512  # regime, na którym stary guard >512 się wykładał


@pytest.mark.django_db
def test_format_pbn_error_renders_v1_structurally_not_raw_json():
    out = str(format_pbn_error(V1_BLOB, "TECH"))
    # strukturalny HTML, NIE surowy blob
    assert "PBNValidationError: HTTP 400" in out
    assert "Szczegóły" in out
    assert "isbn" in out
    assert "{&quot;v&quot;:1" not in out  # nie pokazujemy surowego JSON-a v1


@pytest.mark.django_db
def test_format_pbn_error_v1_meryt_hides_header_shows_details():
    out = str(format_pbn_error(V1_BLOB, "MERYT"))
    assert "HTTP 400" not in out  # nagłówek ukryty dla MERYT
    assert "Szczegóły" in out


def test_parse_pbn_api_error_recognizes_v1():
    result = parse_pbn_api_error(V1_BLOB)
    assert result["is_pbn_api_error"] is True  # KLUCZOWE: nie False
    assert result["error_code"] == 400
    assert result["exception_type"] == "PBNValidationError"
    assert "isbn" in result["error_details_json"]


def test_parse_error_details_recognizes_v1():
    result = parse_error_details(_FakeSent(V1_BLOB))
    assert result["error_code"] == 400
    assert result["error_endpoint"] == "/api/v1/publications"
    assert "isbn" in result["error_details"]


def test_admin_exception_details_recognizes_v1():
    out = SentDataAdmin(SentData, admin.site).exception_details(_FakeSent(V1_BLOB))
    assert "Publikacja o identycznym ISBN" in out


def test_extract_from_komunikat_returns_v1_blob_for_downstream():
    # Dla komunikatu-bloba v1 zwracamy cały blob, żeby parse_pbn_api_error
    # (znający v1) mógł go zinterpretować.
    assert extract_pbn_error_from_komunikat(V1_BLOB) == V1_BLOB


@pytest.mark.django_db
def test_format_pbn_error_does_not_raise_on_hostile_deep_json():
    # Totalność parse() na ścieżce renderowania: głęboki JSON w body legacy.
    hostile = "(400, '/x', '" + "[" * 20000 + "]" * 20000 + "')"
    result = str(format_pbn_error(hostile))  # nie może rzucić RecursionError
    assert isinstance(result, str)
