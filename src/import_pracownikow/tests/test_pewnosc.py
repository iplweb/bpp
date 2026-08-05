from dataclasses import dataclass

from import_common.core.autor import (
    PEWNOSC_IEXACT,
    PEWNOSC_INICJAL,
    PEWNOSC_MIN_AUTOMATYCZNA,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
    STATUS_ZGADYWANIE,
    oblicz_status_pewnosci,
    wybierz_autora_z_kandydatow,
)


@dataclass
class _Kand:
    pewnosc: float


@dataclass
class _KandZAutorem:
    autor: object


def _kandydaci(*pewnosci):
    return [_Kand(p) for p in pewnosci]


def test_brak_gdy_pusta_lista():
    assert oblicz_status_pewnosci([], match_po_id=False) == STATUS_BRAK


def test_twardy_po_id_niezaleznie_od_kandydatow():
    assert oblicz_status_pewnosci([], match_po_id=True) == STATUS_TWARDY
    assert oblicz_status_pewnosci(_kandydaci(0.5), match_po_id=True) == STATUS_TWARDY


def test_twardy_pojedynczy_iexact():
    kand = _kandydaci(PEWNOSC_IEXACT)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_TWARDY


def test_zgadywanie_pojedynczy_powyzej_progu_ponizej_jeden():
    kand = _kandydaci(PEWNOSC_MIN_AUTOMATYCZNA)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_ZGADYWANIE


def test_wielu_remis_na_najwyzszym_tierze():
    kand = _kandydaci(PEWNOSC_IEXACT, PEWNOSC_IEXACT)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_WIELU


def test_wielu_gdy_najlepszy_ponizej_progu():
    kand = _kandydaci(PEWNOSC_INICJAL)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_WIELU


def test_pojedynczy_najwyzszy_nad_reszta_to_nie_remis():
    # top_tier ma DOKŁADNIE 1 (0.85 = PEWNOSC_MIN_AUTOMATYCZNA) mimo drugiego,
    # słabszego kandydata (0.5 = PEWNOSC_INICJAL)
    kand = _kandydaci(PEWNOSC_MIN_AUTOMATYCZNA, PEWNOSC_INICJAL)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_ZGADYWANIE


def test_wybierz_autora_z_kandydatow_dla_twardy_i_zgadywanie():
    kand = [_KandZAutorem("A"), _KandZAutorem("B")]
    assert wybierz_autora_z_kandydatow(kand, STATUS_TWARDY) == "A"
    assert wybierz_autora_z_kandydatow(kand, STATUS_ZGADYWANIE) == "A"


def test_wybierz_autora_z_kandydatow_none_dla_wielu_brak_i_pustych():
    kand = [_KandZAutorem("A"), _KandZAutorem("B")]
    assert wybierz_autora_z_kandydatow(kand, STATUS_WIELU) is None
    assert wybierz_autora_z_kandydatow(kand, STATUS_BRAK) is None
    assert wybierz_autora_z_kandydatow([], STATUS_TWARDY) is None
