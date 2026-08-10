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


@pytest.mark.django_db
def test_wysylka_nie_wola_delete_all_statements(
    wydawnictwo_ciagle, admin_user, uczelnia
):
    """Dodanie gałęzi WYCOFANIE nie mogło przekierować WYSYŁKI.

    Rozgałęzienie siedzi na wspólnej ścieżce ``send_to_pbn()``, więc błąd
    w warunku (albo default pola) zamieniłby zaległą kolejkę wysyłek
    w kolejkę wycofań — i skasował oświadczenia rekordów, których nikt
    nie usuwał.
    """
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        uczelnia=uczelnia,
        operacja=PBN_Export_Queue.Operacja.WYSYLKA,
        wysylke_zakonczono=None,
    )

    sent_data = MagicMock()
    with (
        patch.object(PBN_Export_Queue, "_pozyskaj_klienta_pbn") as mock_klient,
        patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery",
            return_value=(sent_data, ["ok"]),
        ) as mock_send,
    ):
        result = wpis.send_to_pbn()

    assert result == SendStatus.FINISHED_OKAY
    mock_send.assert_called_once()
    # ścieżka WYSYLKA przekazuje uczelnię wpisu (multi-hosted)
    assert mock_send.call_args.kwargs["uczelnia"] == uczelnia
    # klienta wycofania nie budujemy w ogóle
    mock_klient.assert_not_called()


@pytest.mark.django_db
def test_integrity_error_zamowil_nie_udaje_already_enqueued(wydawnictwo_ciagle):
    """Prawdziwy ``IntegrityError`` nie może udawać „już w kolejce".

    ``sprobuj_utowrzyc_wpis`` tłumaczyło KAŻDY ``IntegrityError`` na
    ``AlreadyEnqueuedError``, bo spodziewało się wyłącznie kolizji
    częściowego unikatu. Operacja systemowa (soft-delete z sygnału,
    z celery, ze scalania — bez ``request.user``) trafia jednak w NOT NULL
    na ``zamowil`` i dostawała „ten rekord jest już w kolejce":
    ``zakolejkuj_wycofanie`` zwracało None, oświadczenia zostawały w PBN,
    a operator widział komunikat sugerujący, że wszystko jest w porządku.

    ``zamowil=None`` łamie NOT NULL, a NIE unikat aktywnego wpisu — więc
    MUSI polecieć w górę jako ``IntegrityError``.
    """
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(None, wydawnictwo_ciagle)


@pytest.mark.django_db
def test_zakolejkuj_wycofanie_gate_brak_pbn_uid(wydawnictwo_ciagle, admin_user):
    """Bez PBN UID nic nie poszło do PBN — nie kolejkujemy wycofania."""
    from pbn_export_queue.operacje import zakolejkuj_wycofanie

    assert wydawnictwo_ciagle.pbn_uid_id is None
    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn") as mock_task:
        wpis = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=admin_user)

    assert wpis is None
    assert (
        PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle).count()
        == 0
    )
    mock_task.delay.assert_not_called()


@pytest.mark.django_db
def test_zakolejkuj_wycofanie_tworzy_wpis(wydawnictwo_ciagle, admin_user, uczelnia):
    from pbn_api.models import Publication
    from pbn_export_queue.operacje import zakolejkuj_wycofanie

    wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
    wydawnictwo_ciagle.save()

    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn") as mock_task:
        wpis = zakolejkuj_wycofanie(
            wydawnictwo_ciagle, user=admin_user, uczelnia=uczelnia
        )

    assert wpis is not None
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
    assert wpis.uczelnia == uczelnia
    mock_task.delay.assert_called_once_with(wpis.pk)


@pytest.mark.django_db
def test_zakolejkuj_wysylke_nie_ma_gate_na_pbn_uid(wydawnictwo_ciagle, admin_user):
    """WYSYŁKA celowo NIE ma gate'u na ``pbn_uid``.

    Rekord, który nigdy nie poszedł do PBN, po przywróceniu i tak ma prawo
    pojechać — wysyłka dopiero nadaje PBN UID. Kontrakt PINNED planu fazy
    06 mówi „None gdy brak pbn_uid" dla OBU funkcji; to rozstrzygnięcie
    jest świadomym odejściem, żeby nikt go nie „naprawił" pod tamten opis.
    """
    from pbn_export_queue.operacje import zakolejkuj_wysylke

    assert wydawnictwo_ciagle.pbn_uid_id is None
    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn") as mock_task:
        wpis = zakolejkuj_wysylke(wydawnictwo_ciagle, user=admin_user)

    assert wpis is not None
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    mock_task.delay.assert_called_once_with(wpis.pk)


@pytest.mark.django_db
def test_zakolejkuj_idempotentne(wydawnictwo_ciagle, admin_user):
    """Drugie zlecenie dla tego samego rekordu to no-op, nie błąd."""
    from pbn_api.models import Publication
    from pbn_export_queue.operacje import zakolejkuj_wycofanie

    wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
    wydawnictwo_ciagle.save()

    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"):
        pierwszy = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=admin_user)
        drugi = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=admin_user)

    assert pierwszy is not None
    assert drugi is None
    assert (
        PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle).count()
        == 1
    )


@pytest.mark.django_db
def test_zakolejkuj_wycofanie_bez_usera_uzywa_konta_technicznego(
    wydawnictwo_ciagle, uczelnia
):
    """Soft-delete systemowy (bez zalogowanego użytkownika) MUSI utworzyć wpis.

    ``zamowil`` jest NOT NULL, a sygnał/celery/scalanie nie mają requestu.
    Zwrot ``None`` znaczyłby, że oświadczenia zostaną w PBN.
    """
    from pbn_api.models import Publication
    from pbn_export_queue.operacje import (
        NAZWA_KONTA_TECHNICZNEGO,
        zakolejkuj_wycofanie,
    )

    wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
    wydawnictwo_ciagle.save()

    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"):
        wpis = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=None, uczelnia=uczelnia)

    assert wpis is not None, (
        "systemowy soft-delete MUSI utworzyć wpis wycofania — zwrot None "
        "znaczy, że oświadczenia zostaną w PBN"
    )
    assert wpis.zamowil.username == NAZWA_KONTA_TECHNICZNEGO
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
    assert wpis.zamowil.is_active is False
    assert wpis.zamowil.has_usable_password() is False


@pytest.mark.django_db
def test_konto_techniczne_bez_tokenu_konczy_glosno(wydawnictwo_ciagle, uczelnia):
    """Brak tokenu PBN kończy wpis BŁĘDEM, nie cichym sukcesem.

    Konto techniczne nie ma własnego ``pbn_token``, więc autoryzacja
    w PBN rzuci ``WillNotExportError``. To jest akceptowalne WYŁĄCZNIE
    dlatego, że kończy się głośno — wpis dostaje ``FINISHED_ERROR``
    z błędem merytorycznym i komunikatem wskazującym konfigurację.
    Gdyby kończyło się ``FINISHED_OKAY`` albo cichym ``None``, operator
    myślałby, że oświadczenia zostały wycofane.

    Obejście produkcyjne (bez zmiany kodu): administrator ustawia kontu
    technicznemu ``przedstawiaj_w_pbn_jako`` na konto z ważnym tokenem.

    Test nie odtwarza pełnej ścieżki HTTP, bo ``authorize`` w transporcie
    odpala się dopiero na odpowiedzi 403 — czyli po realnym żądaniu do
    PBN. Sprawdzamy więc to, co faktycznie jest nasze: że wyjątek z
    klienta trafia w klasyfikację jako błąd MERYTORYCZNY.
    """
    from pbn_api.exceptions import WillNotExportError
    from pbn_api.models import Publication
    from pbn_export_queue.models import RodzajBledu
    from pbn_export_queue.operacje import pobierz_konto_techniczne

    wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
    wydawnictwo_ciagle.save()
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=pobierz_konto_techniczne(),
        uczelnia=uczelnia,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        wysylke_zakonczono=None,
    )
    wydawnictwo_ciagle.delete()

    with patch.object(
        PBN_Export_Queue,
        "_pozyskaj_klienta_pbn",
        side_effect=WillNotExportError(
            "Najpierw wykonaj autoryzację w PBN API za pomocą menu"
        ),
    ):
        result = wpis.send_to_pbn()

    assert result == SendStatus.FINISHED_ERROR
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie is False
    assert wpis.rodzaj_bledu == RodzajBledu.MERYTORYCZNY
    assert "autoryzacj" in wpis.komunikat.lower()


@pytest.mark.django_db
def test_pozyskaj_klienta_bierze_token_zamawiajacego(
    wydawnictwo_ciagle, admin_user, uczelnia
):
    """Klient budowany jest z uczelni WPISU i tokenu zamawiającego.

    Nigdy „pierwszej z brzegu" uczelni — w multi-hosted wycofanie dotyczy
    profilu konkretnej instytucji. Token idzie przez ``get_pbn_user()``,
    więc ``przedstawiaj_w_pbn_jako`` działa bez zmiany kodu.
    """
    admin_user.pbn_token = "TOKEN-123"
    admin_user.save()
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        uczelnia=uczelnia,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
    )

    with patch.object(type(uczelnia), "pbn_client") as mock_pbn_client:
        wpis._pozyskaj_klienta_pbn()

    mock_pbn_client.assert_called_once_with("TOKEN-123")
