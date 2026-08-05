import pytest
from model_bakery import baker

from pbn_client.exceptions import PBNValidationError
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu
from pbn_export_queue.views.utils import parse_pbn_api_error

VALIDATION_BODY = (
    '{"code":400,"message":"Bad Request","description":"Validation failed.",'
    '"details":{"openAccess.releaseDate":"Data ... wymagana!"}}'
)


@pytest.mark.django_db
def test_queue_classifies_pbnvalidationerror_as_merytoryczny():
    rec = baker.make(PBN_Export_Queue)
    exc = PBNValidationError(400, "/api/v1/publications", VALIDATION_BODY)

    rec._handle_pbn_exception(exc)

    rec.refresh_from_db()
    assert rec.rodzaj_bledu == RodzajBledu.MERYTORYCZNY


def test_queue_parser_recognizes_pbnvalidationerror_str_small_body():
    # str(exc) = tupla → parse_pbn_api_error rozpoznaje przez
    # looks_like_tuple.
    exc = PBNValidationError(400, "/api/v1/publications", VALIDATION_BODY)
    result = parse_pbn_api_error(str(exc))
    assert result["is_pbn_api_error"] is True


def test_queue_parser_512_boundary_large_body_not_recognized():
    # A3: parse_pbn_api_error ma guard len(message_part) > 512 → bez
    # prefiksu klasy zwraca is_pbn_api_error=False. Pre-existing (dotyczy
    # też HttpException), utrwalone jako świadoma granica — nie regresja
    # tej zmiany.
    big_details = ",".join(
        f'"pole{i}":"Bardzo długi komunikat walidacji {i}"' for i in range(30)
    )
    body = '{"details":{' + big_details + "}}"
    exc = PBNValidationError(400, "/api/v1/publications", body)
    result = parse_pbn_api_error(str(exc))
    assert result["is_pbn_api_error"] is False
