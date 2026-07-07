from datetime import timedelta

from django.utils import timezone

from bpp.models import Jednostka_Rodzic, Wydzial


def _wezel(wydzial):
    """LAZY węzeł-lustro Jednostka dla wydziału (#438) — tworzony przy linku."""
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    return znajdz_lub_utworz_wezel_wydzialu(wydzial)[0]


def test_Wydzial_jednostki(wydzial: Wydzial, jednostka):
    assert jednostka in wydzial.jednostki()


def test_Wydzial_aktualne_jednostki(wydzial: Wydzial, jednostka, yesterday):
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial), jednostka=jednostka, od=yesterday, do=None
    )
    assert jednostka in wydzial.aktualne_jednostki()
    assert jednostka not in wydzial.historyczne_jednostki()
    assert jednostka not in wydzial.kola_naukowe()


def test_Wydzial_historyczne_jednostki(wydzial: Wydzial, jednostka, yesterday):
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=yesterday - timedelta(days=50),
        do=yesterday - timedelta(days=5),
    )
    assert jednostka not in wydzial.aktualne_jednostki()
    assert jednostka in wydzial.historyczne_jednostki()
    assert jednostka not in wydzial.kola_naukowe()


def test_Wydzial_kola_naukowe(wydzial: Wydzial, kolo_naukowe):
    Jednostka_Rodzic.objects.create(parent=_wezel(wydzial), jednostka=kolo_naukowe)
    assert kolo_naukowe in wydzial.kola_naukowe()
    assert kolo_naukowe not in wydzial.aktualne_jednostki()
    assert kolo_naukowe not in wydzial.historyczne_jednostki()


def test_Wydzial_kola_naukowe_historyczne(wydzial: Wydzial, kolo_naukowe):
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=kolo_naukowe,
        do=timezone.now() - timedelta(days=7),
    )
    assert kolo_naukowe not in wydzial.kola_naukowe()
    assert kolo_naukowe not in wydzial.aktualne_jednostki()
    assert kolo_naukowe in wydzial.historyczne_jednostki()
