"""Model ``SoftDeleteLog`` — audyt operacji soft-delete (faza 06, Task 2)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models.soft_delete_log import SoftDeleteLog


@pytest.mark.django_db
def test_softdeletelog_gfk_wskazuje_na_rekord(wydawnictwo_ciagle):
    log = SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(wydawnictwo_ciagle),
        object_id=wydawnictwo_ciagle.pk,
        akcja=SoftDeleteLog.Akcja.DELETE,
        powod="test",
    )
    assert log.content_object == wydawnictwo_ciagle
    assert log.timestamp is not None
    assert log.user is None
    assert log.pbn_queue_entry is None
    assert log.pbn_status == ""


@pytest.mark.django_db
def test_softdeletelog_akcja_choices():
    assert SoftDeleteLog.Akcja.DELETE == "delete"
    assert SoftDeleteLog.Akcja.RESTORE == "restore"
    assert SoftDeleteLog.Akcja.HARD_DELETE == "hard_delete"


@pytest.mark.django_db
def test_softdeletelog_user_set_null(wydawnictwo_ciagle, django_user_model):
    """Skasowanie konta NIE MOŻE zabrać ze sobą wpisów audytu.

    ``SET_NULL``, nie ``CASCADE``: log ma przeżyć odejście pracownika —
    inaczej usunięcie konta wymazywałoby ślad po jego decyzjach, czyli
    dokładnie to, przed czym ten model ma chronić.
    """
    u = baker.make(django_user_model)
    log = SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(wydawnictwo_ciagle),
        object_id=wydawnictwo_ciagle.pk,
        akcja=SoftDeleteLog.Akcja.DELETE,
        user=u,
    )
    u.delete()
    log.refresh_from_db()
    assert log.user is None


@pytest.mark.django_db
def test_softdeletelog_przezywa_twarde_skasowanie_rekordu(wydawnictwo_ciagle):
    """Wpis logu MUSI przetrwać zniknięcie rekordu, którego dotyczy.

    To jest cały powód istnienia GFK zamiast FK: przy ``HARD_DELETE``
    wiersz publikacji znika fizycznie, a log ma zostać jako jedyny ślad,
    że kiedykolwiek istniała. FK z ``CASCADE`` skasowałby dowód razem
    z dowodem winy; FK z ``PROTECT`` zablokowałby samo kasowanie.
    """
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    pk = wydawnictwo_ciagle.pk
    log = SoftDeleteLog.objects.create(
        content_type=ct, object_id=pk, akcja=SoftDeleteLog.Akcja.HARD_DELETE
    )
    wydawnictwo_ciagle.hard_delete()

    log.refresh_from_db()
    assert log.object_id == pk
    assert log.content_object is None
