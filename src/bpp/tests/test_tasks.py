from datetime import timedelta
from unittest.mock import Mock

import pytest
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle
from bpp.tasks import (
    EASYAUDIT_LOGINEVENT_RETENTION_MONTHS,
    _zaktualizuj_liczbe_cytowan,
    usun_stare_logi_logowania_easyaudit,
)


@pytest.mark.django_db
def test_zaktualizuj_liczbe_cytowan(uczelnia, wydawnictwo_ciagle, mocker):

    m = Mock()
    m.query_multiple = Mock(
        return_value=[{wydawnictwo_ciagle.pk: {"timesCited": "31337"}}]
    )

    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    _zaktualizuj_liczbe_cytowan(
        [
            Wydawnictwo_Ciagle,
        ]
    )

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 31337


@pytest.mark.django_db
def test_usun_stare_logi_logowania_easyaudit():
    """Kasuje LoginEvent starsze niż 24 mies., zostawia nowsze, nie rusza
    CRUDEvent (historia edycji)."""
    from easyaudit.models import CRUDEvent, LoginEvent

    now = timezone.now()
    stary = LoginEvent.objects.create(login_type=LoginEvent.LOGIN, username="a")
    nowy = LoginEvent.objects.create(login_type=LoginEvent.LOGIN, username="b")
    crud = CRUDEvent.objects.create(
        event_type=CRUDEvent.CREATE,
        object_repr="x",
        object_id=1,
        content_type_id=1,
    )
    # auto_now_add ustawia datetime na teraz — przestawiamy ręcznie przez update()
    cutoff = now - relativedelta(months=EASYAUDIT_LOGINEVENT_RETENTION_MONTHS)
    LoginEvent.objects.filter(pk=stary.pk).update(datetime=cutoff - timedelta(days=1))
    LoginEvent.objects.filter(pk=nowy.pk).update(datetime=now - timedelta(days=1))

    deleted = usun_stare_logi_logowania_easyaudit()

    assert deleted == 1
    assert not LoginEvent.objects.filter(pk=stary.pk).exists()
    assert LoginEvent.objects.filter(pk=nowy.pk).exists()
    # CRUDEvent nietknięty
    assert CRUDEvent.objects.filter(pk=crud.pk).exists()
