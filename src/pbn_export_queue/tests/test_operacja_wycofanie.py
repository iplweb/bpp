"""Faza 05 soft-delete: wycofanie oświadczeń dyscyplin z PBN.

Soft-delete publikacji, która poszła do PBN, musi wycofać jej oświadczenia
z profilu instytucji. Realizuje to nowa operacja ``WYCOFANIE`` w kolejce
eksportu, obok dotychczasowej ``WYSYLKA``.
"""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue, SendStatus


@pytest.fixture
def wpis_wycofania(wydawnictwo_ciagle, admin_user, uczelnia):
    """Zlecenie wycofania dla publikacji, która poszła do PBN i trafiła
    do kosza — czyli dokładnie sytuacja, w której faza 05 działa.

    Kolejność ma znaczenie: wpis powstaje PRZED skasowaniem rekordu, tak
    jak w produkcji (receiver fazy 06 kolejkuje przy usuwaniu).
    """
    from pbn_api.models import Publication, SentData

    wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
    wydawnictwo_ciagle.save()
    SentData.objects.create(
        object=wydawnictwo_ciagle,
        data_sent={},
        submitted_successfully=True,
        uploaded_okay=True,
        uczelnia=uczelnia,
    )
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        uczelnia=uczelnia,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        wysylke_zakonczono=None,
    )
    wydawnictwo_ciagle.delete()
    return wpis


@pytest.mark.django_db
def test_operacja_default_wysylka(wydawnictwo_ciagle, admin_user):
    """Wpisy sprzed fazy 05 (i wszystkie tworzone bez jawnej operacji)
    muszą nadal znaczyć „wyślij" — inaczej migracja zamieniłaby zaległą
    kolejkę wysyłek w kolejkę wycofań."""
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )
    wpis.refresh_from_db()
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    assert PBN_Export_Queue.Operacja.WYSYLKA == "wysylka"
    assert PBN_Export_Queue.Operacja.WYCOFANIE == "wycofanie"


@pytest.mark.django_db
def test_sentdata_mark_as_withdrawn(wydawnictwo_ciagle, uczelnia):
    """Wycofanie zostawia ślad, przywrócenie go kasuje.

    Wiersza SentData NIE kasujemy: zostaje dla re-matchingu przy restore
    i dla SoftDeleteLog fazy 06. Znacznik ``withdrawn_at`` odróżnia „nigdy
    nie wysłane" od „wysłane, potem wycofane" — sam
    ``submitted_successfully=False`` tych dwóch stanów nie rozróżnia.

    Izolację per-uczelnia sprawdza osobno
    ``pbn_api/tests/test_sentdata_per_uczelnia.py`` (tam mieszka fixture
    ``uczelnia2`` i reszta rodzeństwa tego zachowania).
    """
    from pbn_api.models.sentdata import SentData

    SentData.objects.create(
        object=wydawnictwo_ciagle,
        data_sent={},
        submitted_successfully=True,
        uploaded_okay=True,
        uczelnia=uczelnia,
    )

    SentData.objects.mark_as_withdrawn(wydawnictwo_ciagle, uczelnia=uczelnia)

    sd = SentData.objects.get_for_rec(wydawnictwo_ciagle, uczelnia)
    assert sd.submitted_successfully is False
    assert sd.withdrawn_at is not None

    # restore → ponowna wysyłka zeruje znacznik wycofania
    SentData.objects.mark_as_successful(wydawnictwo_ciagle, uczelnia=uczelnia)
    sd = SentData.objects.get_for_rec(wydawnictwo_ciagle, uczelnia)
    assert sd.submitted_successfully is True
    assert sd.withdrawn_at is None


@pytest.mark.django_db
def test_wycofanie_wola_delete_all_statements(
    wpis_wycofania, wydawnictwo_ciagle, uczelnia
):
    """Gałąź WYCOFANIE dochodzi do klienta PBN i kończy wpis sukcesem.

    ⚠️ Rekord jest w KOSZU (fixture go kasuje) — i to jest cała trudność.
    Do fazy 05 ``send_to_pbn()`` odrzucał takie wpisy guardem
    ``check_if_record_still_exists()``, więc gałąź wycofania byłaby martwym
    kodem. Test bez soft-delete'u przechodziłby także przed poprawką
    i niczego by nie pilnował.
    """
    from pbn_api.models import SentData

    mock_client = MagicMock()
    with patch.object(
        PBN_Export_Queue, "_pozyskaj_klienta_pbn", return_value=mock_client
    ):
        result = wpis_wycofania.send_to_pbn()

    assert result == SendStatus.FINISHED_OKAY
    mock_client.delete_all_publication_statements.assert_called_once_with(
        wydawnictwo_ciagle.pbn_uid_id
    )
    wpis_wycofania.refresh_from_db()
    assert wpis_wycofania.zakonczono_pomyslnie is True
    assert wpis_wycofania.wysylke_zakonczono is not None

    sd = SentData.objects.get_for_rec(wydawnictwo_ciagle, uczelnia)
    assert sd.submitted_successfully is False
    assert sd.withdrawn_at is not None


@pytest.mark.django_db
def test_sprzataczka_nie_kasuje_zlecen_wycofania(
    wydawnictwo_ciagle, wydawnictwo_zwarte, admin_user, uczelnia
):
    """Regresja blokera #2 (rewizja planu 2026-08-10).

    ``kolejka_wyczysc_wpisy_bez_rekordow()`` kasuje wpisy, których rekord
    „już nie istnieje", i używa do tego tego samego guardu co
    ``send_to_pbn()``. Zanim guard poznał operację, soft-delete publikacji
    sprawiał, że sprzątaczka kasowała WŁAŚNIE UTWORZONE zlecenie wycofania:
    oświadczenia zostawały w PBN, śladu brak, a wyścig z workerem celery
    rozstrzygał się losowo.

    Dowodem jest RÓŻNICA między operacjami, nie samo przetrwanie wpisu —
    zachowanie dla WYSYLKI (fazy 02) musi zostać nietknięte.
    """
    from pbn_export_queue.tasks import kolejka_wyczysc_wpisy_bez_rekordow

    wycofanie = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        uczelnia=uczelnia,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        wysylke_zakonczono=None,
    )
    wysylka = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_zwarte,
        zamowil=admin_user,
        uczelnia=uczelnia,
        operacja=PBN_Export_Queue.Operacja.WYSYLKA,
        wysylke_zakonczono=None,
    )

    wydawnictwo_ciagle.delete()
    wydawnictwo_zwarte.delete()

    kolejka_wyczysc_wpisy_bez_rekordow()

    assert PBN_Export_Queue.objects.filter(pk=wycofanie.pk).exists(), (
        "sprzątaczka skasowała zlecenie WYCOFANIA — oświadczenia zostaną "
        "w PBN i nikt się o tym nie dowie"
    )
    assert not PBN_Export_Queue.objects.filter(pk=wysylka.pk).exists(), (
        "wpis WYSYLKA rekordu z kosza ma nadal znikać — to zachowanie "
        "z fazy 02, którego nie wolno zepsuć przy okazji"
    )
