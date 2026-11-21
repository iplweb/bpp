import pytest

from bpp.admin.actions import (
    ustaw_po_korekcie,
    ustaw_przed_korekta,
    ustaw_w_trakcie_korekty,
)
from bpp.models import Wydawnictwo_Zwarte


class FakeModelAdmin:
    def message_user(self, *args, **kw):
        pass


class FakeRequest:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
def test_ustaw_przed_korekta(wydawnictwo_zwarte_po_korekcie, przed_korekta, admin_user):
    ustaw_przed_korekta(
        FakeModelAdmin(), FakeRequest(admin_user), Wydawnictwo_Zwarte.objects.all()
    )
    wydawnictwo_zwarte_po_korekcie.refresh_from_db()
    assert wydawnictwo_zwarte_po_korekcie.status_korekty == przed_korekta


@pytest.mark.django_db
def test_ustaw_po_korekcie(wydawnictwo_zwarte_przed_korekta, po_korekcie, admin_user):
    ustaw_po_korekcie(
        FakeModelAdmin(), FakeRequest(admin_user), Wydawnictwo_Zwarte.objects.all()
    )
    wydawnictwo_zwarte_przed_korekta.refresh_from_db()
    assert wydawnictwo_zwarte_przed_korekta.status_korekty == po_korekcie


@pytest.mark.django_db
def test_ustaw_w_trakcie_korekty(
    wydawnictwo_zwarte_przed_korekta, w_trakcie_korekty, admin_user
):
    ustaw_w_trakcie_korekty(
        FakeModelAdmin(), FakeRequest(admin_user), Wydawnictwo_Zwarte.objects.all()
    )
    wydawnictwo_zwarte_przed_korekta.refresh_from_db()
    assert wydawnictwo_zwarte_przed_korekta.status_korekty == w_trakcie_korekty
