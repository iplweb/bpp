from datetime import timedelta

from django.utils import timezone

from bpp.models import Jednostka_Wydzial, Wydzial


def test_Wydzial_jednostki(wydzial: Wydzial, jednostka):
    assert jednostka in wydzial.jednostki()


def test_Wydzial_aktualne_jednostki(wydzial: Wydzial, jednostka, yesterday):
    Jednostka_Wydzial.objects.create(
        wydzial=wydzial, jednostka=jednostka, od=yesterday, do=None
    )
    assert jednostka in wydzial.aktualne_jednostki()
    assert jednostka not in wydzial.historyczne_jednostki()
    assert jednostka not in wydzial.kola_naukowe()


def test_Wydzial_historyczne_jednostki(wydzial: Wydzial, jednostka, yesterday):
    Jednostka_Wydzial.objects.create(
        wydzial=wydzial,
        jednostka=jednostka,
        od=yesterday - timedelta(days=50),
        do=yesterday - timedelta(days=5),
    )
    assert jednostka not in wydzial.aktualne_jednostki()
    assert jednostka in wydzial.historyczne_jednostki()
    assert jednostka not in wydzial.kola_naukowe()


def test_Wydzial_kola_naukowe(wydzial: Wydzial, kolo_naukowe):
    Jednostka_Wydzial.objects.create(wydzial=wydzial, jednostka=kolo_naukowe)
    assert kolo_naukowe in wydzial.kola_naukowe()
    assert kolo_naukowe not in wydzial.aktualne_jednostki()
    assert kolo_naukowe not in wydzial.historyczne_jednostki()


def test_Wydzial_kola_naukowe_historyczne(wydzial: Wydzial, kolo_naukowe):
    Jednostka_Wydzial.objects.create(
        wydzial=wydzial, jednostka=kolo_naukowe, do=timezone.now() - timedelta(days=7)
    )
    assert kolo_naukowe not in wydzial.kola_naukowe()
    assert kolo_naukowe not in wydzial.aktualne_jednostki()
    assert kolo_naukowe in wydzial.historyczne_jednostki()
