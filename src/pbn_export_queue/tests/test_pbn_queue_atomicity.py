"""Testy atomowości kolejki eksportu PBN (finding #2 z security review).

Sprawdzają, że:
  * częściowy unikat blokuje drugi aktywny wpis dla tego samego rekordu,
  * wyścig w ``sprobuj_utowrzyc_wpis`` kończy się domenowym
    ``AlreadyEnqueuedError`` (nie surowym ``IntegrityError``),
  * ``prepare_for_resend`` odmawia uaktywnienia zakończonego wpisu, gdy
    istnieje już inny aktywny wpis dla tego rekordu,
  * ``_zajmij_atomowo`` faktycznie zajmuje wpis / sygnalizuje jego brak.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from pbn_api.exceptions import AlreadyEnqueuedError
from pbn_export_queue.models import PBN_Export_Queue, SendStatus


def _ct(obj):
    return ContentType.objects.get_for_model(obj)


@pytest.mark.django_db
def test_constraint_blokuje_drugi_aktywny_wpis(wydawnictwo_ciagle, admin_user):
    """Częściowy unikat: co najwyżej jeden aktywny wpis na rekord."""
    ct = _ct(wydawnictwo_ciagle)
    PBN_Export_Queue.objects.create(
        content_type=ct, object_id=wydawnictwo_ciagle.pk, zamowil=admin_user
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PBN_Export_Queue.objects.create(
                content_type=ct, object_id=wydawnictwo_ciagle.pk, zamowil=admin_user
            )


@pytest.mark.django_db
def test_constraint_dopuszcza_wiele_zakonczonych(wydawnictwo_ciagle, admin_user):
    """Zakończone wpisy (wysylke_zakonczono != NULL) nie podlegają unikatowi."""
    ct = _ct(wydawnictwo_ciagle)
    for _ in range(3):
        PBN_Export_Queue.objects.create(
            content_type=ct,
            object_id=wydawnictwo_ciagle.pk,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )
    assert (
        PBN_Export_Queue.objects.filter(
            content_type=ct, object_id=wydawnictwo_ciagle.pk
        ).count()
        == 3
    )


@pytest.mark.django_db
def test_sprobuj_utowrzyc_wpis_wyscig_daje_alreadyenqueued(
    wydawnictwo_ciagle, admin_user, mocker
):
    """Symulacja wyścigu: exists() nie widzi wpisu, ale constraint blokuje
    create() → AlreadyEnqueuedError zamiast IntegrityError."""
    ct = _ct(wydawnictwo_ciagle)
    PBN_Export_Queue.objects.create(
        content_type=ct, object_id=wydawnictwo_ciagle.pk, zamowil=admin_user
    )
    # exists() zwraca False (jakby aktywnego wpisu nie było) — wymuszamy tor
    # create(), który trafi w unikat bazy.
    mocker.patch(
        "pbn_export_queue.models.PBN_Export_QueueManager.filter_rekord_do_wysylki",
        return_value=PBN_Export_Queue.objects.none(),
    )
    with pytest.raises(AlreadyEnqueuedError):
        PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(admin_user, wydawnictwo_ciagle)


@pytest.mark.django_db
def test_prepare_for_resend_odmawia_gdy_istnieje_inny_aktywny(
    wydawnictwo_ciagle, admin_user
):
    ct = _ct(wydawnictwo_ciagle)
    zakonczony = PBN_Export_Queue.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle.pk,
        zamowil=admin_user,
        wysylke_zakonczono=timezone.now(),
    )
    PBN_Export_Queue.objects.create(  # inny aktywny wpis dla tego rekordu
        content_type=ct, object_id=wydawnictwo_ciagle.pk, zamowil=admin_user
    )
    with pytest.raises(AlreadyEnqueuedError):
        zakonczony.prepare_for_resend(user=admin_user)


@pytest.mark.django_db
def test_prepare_for_resend_reaktywuje_gdy_brak_innych(
    wydawnictwo_ciagle, admin_user
):
    ct = _ct(wydawnictwo_ciagle)
    zakonczony = PBN_Export_Queue.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle.pk,
        zamowil=admin_user,
        wysylke_zakonczono=timezone.now(),
        zakonczono_pomyslnie=True,
    )
    zakonczony.prepare_for_resend(user=admin_user)
    zakonczony.refresh_from_db()
    assert zakonczony.wysylke_zakonczono is None


@pytest.mark.django_db
def test_zajmij_atomowo_zajmuje_i_zwieksza_prob(wydawnictwo_ciagle, admin_user):
    ct = _ct(wydawnictwo_ciagle)
    wpis = PBN_Export_Queue.objects.create(
        content_type=ct, object_id=wydawnictwo_ciagle.pk, zamowil=admin_user
    )
    assert wpis._zajmij_atomowo() is True
    wpis.refresh_from_db()
    assert wpis.wysylke_podjeto is not None
    assert wpis.ilosc_prob == 1


@pytest.mark.django_db
def test_send_to_pbn_locked_elsewhere_gdy_zakonczony_w_miedzyczasie(
    wydawnictwo_ciagle, admin_user, mocker
):
    """Gdy wpis zostanie zakończony między refresh a zajęciem wiersza,
    _zajmij_atomowo zwróci False, a send_to_pbn → LOCKED_ELSEWHERE."""
    ct = _ct(wydawnictwo_ciagle)
    wpis = PBN_Export_Queue.objects.create(
        content_type=ct, object_id=wydawnictwo_ciagle.pk, zamowil=admin_user
    )
    mocker.patch.object(wpis, "check_if_record_still_exists", return_value=True)
    mocker.patch.object(wpis, "_zajmij_atomowo", return_value=False)
    assert wpis.send_to_pbn() == SendStatus.LOCKED_ELSEWHERE
