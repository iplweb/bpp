from bpp.admin.actions import (
    ustaw_po_korekcie,
    ustaw_przed_korekta,
    ustaw_w_trakcie_korekty,
)
from bpp.models import Wydawnictwo_Zwarte


class FakeModelAdmin:
    def message_user(self, *args, **kw):
        pass


def test_ustaw_przed_korekta(wydawnictwo_zwarte_po_korekcie, przed_korekta):
    ustaw_przed_korekta(FakeModelAdmin(), None, Wydawnictwo_Zwarte.objects.all())
    wydawnictwo_zwarte_po_korekcie.refresh_from_db()
    assert wydawnictwo_zwarte_po_korekcie.status_korekty == przed_korekta


def test_ustaw_po_korekcie(wydawnictwo_zwarte_przed_korekta, po_korekcie):
    ustaw_po_korekcie(FakeModelAdmin(), None, Wydawnictwo_Zwarte.objects.all())
    wydawnictwo_zwarte_przed_korekta.refresh_from_db()
    assert wydawnictwo_zwarte_przed_korekta.status_korekty == po_korekcie


def test_ustaw_w_trakcie_korekty(wydawnictwo_zwarte_przed_korekta, w_trakcie_korekty):
    ustaw_w_trakcie_korekty(FakeModelAdmin(), None, Wydawnictwo_Zwarte.objects.all())
    wydawnictwo_zwarte_przed_korekta.refresh_from_db()
    assert wydawnictwo_zwarte_przed_korekta.status_korekty == w_trakcie_korekty
