"""Nieważny token użytkownika PBN -> prośba o autoryzację, nie surowy błąd.

Rollbar #5336: PBN odpowiedział na POST 403 gołym tekstem ("W celu
poprawnej autentykacji należy podać poprawny token..."), a użytkownik
zobaczył generyczny błąd z wartością tokena zamiast linku do autoryzacji.
"""

from unittest.mock import MagicMock

import pytest
from pbn_client.const import NEEDS_PBN_AUTH_MSG
from pbn_client.transport import RequestsTransport

from bpp.admin.helpers.pbn_api.common import sprobuj_wyslac_do_pbn
from pbn_api.client import BppPBNClient

TEKST_403 = (
    NEEDS_PBN_AUTH_MSG + " Podany token użytkownika abc123 w ramach aplikacji "
    "BPP@TEST nie istnieje lub został unieważniony!"
)


class _Odpowiedz403:
    status_code = 403
    headers = {"Content-Type": "text/plain"}
    content = TEKST_403.encode("utf-8")
    text = TEKST_403

    def json(self):
        raise ValueError("to nie jest JSON")


@pytest.mark.django_db
def test_wysylka_403_tekstem_prosi_o_autoryzacje(
    mocker, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, uczelnia
):
    mocker.patch("pbn_client.transport.requests.post", return_value=_Odpowiedz403())
    mocker.patch("pbn_client.transport.requests.get", return_value=_Odpowiedz403())

    transport = RequestsTransport("app", "apptok", "https://pbn.example", "abc123")
    klient = BppPBNClient(transport=transport, uczelnia=uczelnia)
    notificator = MagicMock()

    sprobuj_wyslac_do_pbn(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, klient, uczelnia, notificator
    )

    komunikaty = " ".join(str(c) for c in notificator.method_calls)
    assert "wymagana autoryzacja w PBN" in komunikaty
    assert "abc123" not in komunikaty
    notificator.error.assert_not_called()
