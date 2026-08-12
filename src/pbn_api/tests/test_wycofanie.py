"""Prymityw wycofania oświadczeń dyscyplin z PBN (faza 05 soft-delete).

Wycofanie ma DWA wejścia: asynchroniczne (kolejka ``pbn_export_queue``)
i synchroniczne (``synchronizuj_publikacje``, poza kolejką). Oba muszą
zostawiać identyczny stan ``SentData`` i identycznie rozumieć, co znaczy
sukces — dlatego logika mieszka w jednej wolnostojącej funkcji, a nie
w metodzie modelu kolejki.

Podział odpowiedzialności (niezmiennik §4.2 specu): prymityw odpowiada za
semantykę „co znaczy sukces" i za stan ``SentData``; wywołujący — za
klasyfikację wyjątków i politykę ponawiania. Dlatego wyjątki PBN lecą stąd
w górę nietknięte.
"""

from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    HttpException,
    PraceSerwisoweException,
)
from pbn_api.models import Publication, SentData
from pbn_api.wycofanie import (
    StatusWycofania,
    wycofaj_oswiadczenia,
)


@pytest.fixture
def publikacja_w_pbn(wydawnictwo_ciagle):
    """Publikacja, która realnie poszła do PBN (ma nadany PBN UID)."""
    wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
    wydawnictwo_ciagle.save()
    return wydawnictwo_ciagle


@pytest.fixture
def sent_data(publikacja_w_pbn, uczelnia):
    return SentData.objects.create(
        object=publikacja_w_pbn,
        data_sent={},
        submitted_successfully=True,
        uploaded_okay=True,
        uczelnia=uczelnia,
    )


@pytest.mark.django_db
def test_wycofanie_wola_klienta_i_oznacza_sentdata(
    publikacja_w_pbn, sent_data, uczelnia
):
    client = MagicMock()

    wynik = wycofaj_oswiadczenia(publikacja_w_pbn, client, uczelnia=uczelnia)

    assert wynik.status == StatusWycofania.WYCOFANO
    client.delete_all_publication_statements.assert_called_once_with(
        publikacja_w_pbn.pbn_uid_id
    )
    sd = SentData.objects.get_for_rec(publikacja_w_pbn, uczelnia)
    assert sd.submitted_successfully is False
    assert sd.withdrawn_at is not None


@pytest.mark.django_db
def test_brak_oswiadczen_to_sukces(publikacja_w_pbn, sent_data, uczelnia):
    """``CannotDeleteStatementsException`` znaczy „nie było czego usuwać".

    To zaległa pułapka: pakiet ``pbn-client`` ponawia na tym wyjątku
    w ``_delete_statements_with_retry``, bo tam kasowanie poprzedza WYSYŁKĘ
    i brak oświadczeń jest przeszkodą. U nas stan docelowy („w PBN nie ma
    oświadczeń tej publikacji") jest wtedy JUŻ osiągnięty — ponawianie
    dokładałoby ruchu i kończyło się błędem zamiast sukcesem.
    """
    client = MagicMock()
    client.delete_all_publication_statements.side_effect = (
        CannotDeleteStatementsException("brak oświadczeń")
    )

    wynik = wycofaj_oswiadczenia(publikacja_w_pbn, client, uczelnia=uczelnia)

    assert wynik.status == StatusWycofania.BRAK_OSWIADCZEN
    sd = SentData.objects.get_for_rec(publikacja_w_pbn, uczelnia)
    assert sd.submitted_successfully is False
    assert sd.withdrawn_at is not None


@pytest.mark.django_db
def test_brak_pbn_uid_pomija_bez_wolania_klienta(wydawnictwo_ciagle, uczelnia):
    """Bez PBN UID nic do PBN nie poszło — nie ma czego wycofywać."""
    client = MagicMock()
    assert wydawnictwo_ciagle.pbn_uid_id is None

    wynik = wycofaj_oswiadczenia(wydawnictwo_ciagle, client, uczelnia=uczelnia)

    assert wynik.status == StatusWycofania.POMINIETO
    client.delete_all_publication_statements.assert_not_called()


@pytest.mark.django_db
def test_brak_wiersza_sentdata_to_nadal_sukces(publikacja_w_pbn, uczelnia):
    """Rekord ma PBN UID, ale nigdy nie było wiersza SentData.

    Zdarza się przy rekordach zaimportowanych z PBN (UID przyszedł
    z importu, nie z wysyłki). Oświadczenia i tak trzeba usunąć, a brak
    wiersza nie jest błędem — nie ma po prostu czego oznaczać.
    """
    assert not SentData.objects.filter(object_id=publikacja_w_pbn.pk).exists()
    client = MagicMock()

    wynik = wycofaj_oswiadczenia(publikacja_w_pbn, client, uczelnia=uczelnia)

    assert wynik.status == StatusWycofania.WYCOFANO
    client.delete_all_publication_statements.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "wyjatek",
    [
        PraceSerwisoweException("okno serwisowe"),
        HttpException(423, "url", "zasób zablokowany"),
    ],
    ids=["prace_serwisowe", "http"],
)
def test_wyjatki_pbn_leca_w_gore_bez_dotykania_sentdata(
    publikacja_w_pbn, sent_data, uczelnia, wyjatek
):
    """Prymityw NIE klasyfikuje wyjątków — robi to wywołujący.

    Gdyby połykał je tutaj, kolejka i ścieżka synchroniczna miałyby dwie
    rozjeżdżające się tabele decyzji o ponawianiu. Stan ``SentData`` musi
    zostać nietknięty: wycofanie się nie udało, więc oświadczenia nadal
    są w PBN i rekord nadal jest „wysłany".
    """
    client = MagicMock()
    client.delete_all_publication_statements.side_effect = wyjatek

    with pytest.raises(type(wyjatek)):
        wycofaj_oswiadczenia(publikacja_w_pbn, client, uczelnia=uczelnia)

    sd = SentData.objects.get_for_rec(publikacja_w_pbn, uczelnia)
    assert sd.submitted_successfully is True
    assert sd.withdrawn_at is None
