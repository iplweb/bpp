from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_api.tests.utils import middleware
from pbn_export_queue.models import PBN_Export_Queue

from django.contrib.messages import get_messages

from bpp.admin.helpers.pbn_api.gui import sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui
from bpp.const import RODZAJ_PBN_ARTYKUL
from bpp.models import Charakter_Formalny


@pytest.mark.django_db
def test_sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui_success(
    rf, wydawnictwo_ciagle, admin_user, uczelnia
):
    """Test successful creation of PBN export queue entry with proper link generation"""
    req = rf.get("/")
    req.user = admin_user

    # Ensure the publication has a character that supports PBN export
    wydawnictwo_ciagle.charakter_formalny = baker.make(
        Charakter_Formalny, rodzaj_pbn=RODZAJ_PBN_ARTYKUL
    )
    wydawnictwo_ciagle.save()

    # Configure university for PBN integration
    uczelnia.pbn_integracja = True
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.save()

    with middleware(req):
        with patch(
            "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay_on_commit"
        ) as mock_task:
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(req, wydawnictwo_ciagle)

    # Check that queue entry was created
    queue_entry = PBN_Export_Queue.objects.get(
        content_type__model="wydawnictwo_ciagle",
        object_id=wydawnictwo_ciagle.pk,
        zamowil=admin_user,
    )
    assert queue_entry is not None
    assert queue_entry.rekord_do_wysylki == wydawnictwo_ciagle

    # Check that background task was called
    mock_task.assert_called_once_with(queue_entry.pk)

    # Check messages contain proper link
    messages = list(get_messages(req))
    assert len(messages) == 1
    message = messages[0].message

    # Verify the link contains the proper admin URL
    expected_link = reverse(
        "admin:pbn_export_queue_pbn_export_queue_change", args=(queue_entry.pk,)
    )
    assert expected_link in message
    assert f"Utworzono zlecenie wysyłki rekordu {wydawnictwo_ciagle}" in message
    assert "Kliknij tutaj, aby śledzić stan" in message


@pytest.mark.django_db
def test_sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui_already_enqueued(
    rf, wydawnictwo_ciagle, admin_user, uczelnia
):
    """Test handling when record is already in export queue"""
    req = rf.get("/")
    req.user = admin_user

    # Ensure the publication has a character that supports PBN export
    wydawnictwo_ciagle.charakter_formalny = baker.make(
        Charakter_Formalny, rodzaj_pbn=RODZAJ_PBN_ARTYKUL
    )
    wydawnictwo_ciagle.save()

    # Configure university for PBN integration
    uczelnia.pbn_integracja = True
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.save()

    # Create existing queue entry
    existing_entry = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        wysylke_zakonczono=None,
    )

    with middleware(req):
        with patch(
            "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay_on_commit"
        ) as mock_task:
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(req, wydawnictwo_ciagle)

    # Check that no new queue entry was created
    assert PBN_Export_Queue.objects.filter(pk=existing_entry.pk).count() == 1
    assert PBN_Export_Queue.objects.count() == 1

    # Check that background task was NOT called
    mock_task.assert_not_called()

    # Check warning message
    messages = list(get_messages(req))
    assert len(messages) == 1
    assert (
        f"Rekord {wydawnictwo_ciagle} jest już w kolejce do eksportu do PBN"
        in messages[0].message
    )


@pytest.mark.django_db
def test_sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui_character_not_supported(
    rf, wydawnictwo_ciagle, admin_user
):
    """Test early return when character formal is not supported for PBN export"""
    req = rf.get("/")
    req.user = admin_user

    # Set character that doesn't support PBN export
    wydawnictwo_ciagle.charakter_formalny = baker.make(
        Charakter_Formalny, rodzaj_pbn=None
    )
    wydawnictwo_ciagle.save()

    with middleware(req):
        with patch(
            "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay_on_commit"
        ) as mock_task:
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(req, wydawnictwo_ciagle)

    # Check that no queue entry was created
    assert PBN_Export_Queue.objects.count() == 0

    # Check that background task was NOT called
    mock_task.assert_not_called()

    # Check info message about character not being exported
    messages = list(get_messages(req))
    assert len(messages) == 1
    assert (
        "nie będzie eksportowany do PBN zgodnie z ustawieniem dla charakteru formalnego"
        in messages[0].message
    )


@pytest.mark.django_db
def test_sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui_university_integration_disabled(
    rf, wydawnictwo_ciagle, admin_user, uczelnia
):
    """Test handling when university has PBN integration disabled"""
    req = rf.get("/")
    req.user = admin_user

    # Ensure the publication has a character that supports PBN export
    wydawnictwo_ciagle.charakter_formalny = baker.make(
        Charakter_Formalny, rodzaj_pbn=RODZAJ_PBN_ARTYKUL
    )
    wydawnictwo_ciagle.save()

    # Configure university with disabled PBN integration
    uczelnia.pbn_integracja = False
    uczelnia.pbn_aktualizuj_na_biezaco = False
    uczelnia.save()

    with middleware(req):
        with patch(
            "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay_on_commit"
        ) as mock_task:
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(req, wydawnictwo_ciagle)

    # Check that no queue entry was created
    assert PBN_Export_Queue.objects.count() == 0

    # Check that background task was NOT called
    mock_task.assert_not_called()

    # Check error message about disabled integration
    messages = list(get_messages(req))
    assert len(messages) == 1
    assert "Wysyłka do PBN nie skonfigurowana w obiektu Uczelnia" in messages[0].message
