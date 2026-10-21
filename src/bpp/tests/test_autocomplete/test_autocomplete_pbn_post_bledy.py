"""Obsługa błędów PBN w ``BasePBNAutocomplete.post`` (Rollbar #5366).

Użytkownik wpisuje UID rekordu, którego w PBN nie ma — PBN odpowiada 422
„was not exists!", ``pbn_client`` rzuca ``PublicationNotFound``. To nie jest
błąd aplikacji, więc: przyjazny komunikat dla użytkownika i ŻADNEGO raportu
do Rollbara.
"""

import json
from unittest import mock

import pytest

from bpp.const import PBN_UID_LEN
from bpp.views.autocomplete.pbn_api import (
    JournalAutocomplete,
    PublicationAutocomplete,
)
from pbn_api.client import PBN_GET_PUBLICATION_BY_ID_URL
from pbn_api.exceptions import (
    HttpException,
    NeedsPBNAuthorisationException,
    PraceSerwisoweException,
    PublicationNotFound,
)

UID = "a" * PBN_UID_LEN


def _post(ac_class, rf, user):
    request = rf.post("/", data={"text": UID})
    request.user = user
    return ac_class.as_view()(request)


@pytest.mark.django_db
def test_post_publication_not_found_end_to_end(
    pbn_uczelnia, pbn_client, rf, admin_user, pbn_serwer
):
    tresc = f"Publication with ID {UID} was not exists!"
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID)
    ).respond_with_json(
        {"code": 422, "message": tresc, "description": tresc}, status=422
    )

    with mock.patch("rollbar.report_exc_info") as rollbar_mock:
        res = _post(PublicationAutocomplete, rf, admin_user)

    assert res.status_code == 200
    dane = json.loads(res.content)
    assert dane["id"] is None
    assert UID in dane["text"]
    assert "nie ma" in dane["text"]
    rollbar_mock.assert_not_called()


@pytest.mark.parametrize("status", [404, 422])
@pytest.mark.django_db
def test_post_http_4xx_przyjazny_komunikat_bez_rollbara(rf, admin_user, status):
    exc = HttpException(status, "/api/v1/journals/x", '{"message": "Nie ma"}')
    with (
        mock.patch.object(JournalAutocomplete, "create_object", side_effect=exc),
        mock.patch("rollbar.report_exc_info") as rollbar_mock,
    ):
        res = _post(JournalAutocomplete, rf, admin_user)

    assert res.status_code == 200
    dane = json.loads(res.content)
    assert dane["id"] is None
    assert str(status) in dane["text"]
    assert "Nie ma" in dane["text"]
    rollbar_mock.assert_not_called()


@pytest.mark.django_db
def test_post_http_5xx_komunikat_i_rollbar(rf, admin_user):
    exc = HttpException(502, "/api/v1/journals/x", "Bad Gateway")
    with (
        mock.patch.object(JournalAutocomplete, "create_object", side_effect=exc),
        mock.patch("rollbar.report_exc_info") as rollbar_mock,
    ):
        res = _post(JournalAutocomplete, rf, admin_user)

    assert res.status_code == 200
    dane = json.loads(res.content)
    assert dane["id"] is None
    assert "502" in dane["text"]
    rollbar_mock.assert_called_once()


@pytest.mark.django_db
def test_post_publication_not_found_mock(rf, admin_user):
    exc = PublicationNotFound(422, "/x", "was not exists!")
    with (
        mock.patch.object(PublicationAutocomplete, "create_object", side_effect=exc),
        mock.patch("rollbar.report_exc_info") as rollbar_mock,
    ):
        res = _post(PublicationAutocomplete, rf, admin_user)

    dane = json.loads(res.content)
    assert dane["id"] is None
    assert UID in dane["text"]
    rollbar_mock.assert_not_called()


@pytest.mark.django_db
def test_post_needs_pbn_authorisation(rf, admin_user):
    exc = NeedsPBNAuthorisationException(403, "/x", "auth")
    with (
        mock.patch.object(JournalAutocomplete, "create_object", side_effect=exc),
        mock.patch("rollbar.report_exc_info") as rollbar_mock,
    ):
        res = _post(JournalAutocomplete, rf, admin_user)

    dane = json.loads(res.content)
    assert dane["id"] is None
    assert "Autoryzuj" in dane["text"]
    rollbar_mock.assert_not_called()


@pytest.mark.django_db
def test_post_prace_serwisowe(rf, admin_user):
    with (
        mock.patch.object(
            JournalAutocomplete,
            "create_object",
            side_effect=PraceSerwisoweException(),
        ),
        mock.patch("rollbar.report_exc_info") as rollbar_mock,
    ):
        res = _post(JournalAutocomplete, rf, admin_user)

    dane = json.loads(res.content)
    assert dane["id"] is None
    assert "prace serwisowe" in dane["text"]
    rollbar_mock.assert_not_called()
