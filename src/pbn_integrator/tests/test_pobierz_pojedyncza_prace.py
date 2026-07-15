"""Regresja: 422 „publication not exists" musi rzucać ``BrakIDPracyPoStroniePBN``.

Wcześniej ``_pobierz_pojedyncza_prace`` przy realnym 422-not-exists robiło
``raise BrakIDPracyPoStroniePBN(e)`` — ale ta klasa dziedziczy po
``HttpException`` (konstruktor ``(status_code, url, content)``), więc jedno-
argumentowe wywołanie kończyło się ``TypeError`` ZANIM właściwy wyjątek został
podniesiony. Dodatkowo ``e.content`` bywa ``bytes`` (``smart_content`` zwraca
surowe bajty przy ``UnicodeDecodeError``), przez co samo ``... in e.content``
rzucało ``TypeError`` jeszcze wcześniej.
"""

from unittest.mock import MagicMock

import pytest


def _client_raising(exc):
    client = MagicMock()
    client.get_publication_by_id.side_effect = exc
    return client


def test_422_not_exists_raises_brak_id_not_typeerror():
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, HttpException
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    exc = HttpException(
        422, "https://pbn/x", f"Publication with ID {pub_id} was not exists!"
    )
    with pytest.raises(BrakIDPracyPoStroniePBN):
        publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)


def test_422_not_exists_with_bytes_content_raises_brak_id():
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, HttpException
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    content = f"Publication with ID {pub_id} was not exists!".encode()
    exc = HttpException(422, "https://pbn/x", content)
    with pytest.raises(BrakIDPracyPoStroniePBN):
        publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)


def test_brak_id_preserves_http_fields():
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, HttpException
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    content = f"Publication with ID {pub_id} was not exists!"
    exc = HttpException(422, "https://pbn/x", content)
    with pytest.raises(BrakIDPracyPoStroniePBN) as ei:
        publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)
    assert ei.value.status_code == 422
    assert ei.value.url == "https://pbn/x"
    assert ei.value.content == content
