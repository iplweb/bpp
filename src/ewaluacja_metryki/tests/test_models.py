from decimal import Decimal

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka
from ewaluacja_metryki.models import MetrykaAutora, StatusGenerowania


@pytest.mark.django_db
def test_metryka_autora_create():
    """Test tworzenia MetrykaAutora"""
    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    jednostka = baker.make(Jednostka)

    metryka = MetrykaAutora.objects.create(
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.5"),
        punkty_nazbierane=Decimal("140.0"),
        prace_nazbierane=[1, 2, 3],
        slot_wszystkie=Decimal("5.0"),
        punkty_wszystkie=Decimal("150.0"),
        prace_wszystkie=[1, 2, 3, 4, 5],
        liczba_prac_wszystkie=5,
    )

    assert metryka.autor == autor
    assert metryka.dyscyplina_naukowa == dyscyplina
    assert metryka.jednostka == jednostka
    assert metryka.slot_maksymalny == Decimal("4.0")
    assert metryka.slot_nazbierany == Decimal("3.5")
    assert metryka.punkty_nazbierane == Decimal("140.0")
    assert len(metryka.prace_nazbierane) == 3
    assert metryka.liczba_prac_wszystkie == 5


@pytest.mark.django_db
def test_metryka_autora_wyliczenia():
    """Test automatycznych wyliczeń średnich i procentów"""
    metryka = baker.make(
        MetrykaAutora,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("5.0"),
        punkty_wszystkie=Decimal("150.0"),
    )

    # Sprawdź średnie
    assert metryka.srednia_za_slot_nazbierana == Decimal("40.0")  # 120/3
    assert metryka.srednia_za_slot_wszystkie == Decimal("30.0")  # 150/5

    # Sprawdź procent wykorzystania
    assert metryka.procent_wykorzystania_slotow == Decimal("75.0")  # 3/4 * 100


@pytest.mark.django_db
def test_metryka_autora_slot_niewykorzystany():
    """Test obliczania niewykorzystanych slotów"""
    metryka = baker.make(
        MetrykaAutora, slot_maksymalny=Decimal("4.0"), slot_nazbierany=Decimal("2.5")
    )

    assert metryka.slot_niewykorzystany == Decimal("1.5")


@pytest.mark.django_db
def test_metryka_autora_czy_pelne_wykorzystanie():
    """Test sprawdzania pełnego wykorzystania slotów"""
    metryka_pelna = baker.make(
        MetrykaAutora,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("4.0"),
        punkty_nazbierane=Decimal("160.0"),
        slot_wszystkie=Decimal("4.0"),
        punkty_wszystkie=Decimal("160.0"),
    )

    assert metryka_pelna.czy_pelne_wykorzystanie is True

    metryka_niepelna = baker.make(
        MetrykaAutora,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("120.0"),
    )

    assert metryka_niepelna.czy_pelne_wykorzystanie is False


@pytest.mark.django_db
def test_status_generowania_singleton():
    """Test że StatusGenerowania działa jako singleton"""
    status1 = StatusGenerowania.get_or_create()
    status2 = StatusGenerowania.get_or_create()

    assert status1.pk == 1
    assert status2.pk == 1
    assert status1.pk == status2.pk

    # Próba utworzenia nowego też da pk=1
    status3 = StatusGenerowania()
    status3.save()
    assert status3.pk == 1


@pytest.mark.django_db
def test_status_generowania_rozpocznij():
    """Test rozpoczynania generowania"""
    status = StatusGenerowania.get_or_create()
    status.rozpocznij_generowanie(task_id="test-task-123")

    assert status.w_trakcie is True
    assert status.task_id == "test-task-123"
    assert status.data_rozpoczecia is not None
    assert status.data_zakonczenia is None
    assert status.liczba_przetworzonych == 0
    assert status.liczba_bledow == 0


@pytest.mark.django_db
def test_status_generowania_zakoncz():
    """Test kończenia generowania"""
    status = StatusGenerowania.get_or_create()
    status.rozpocznij_generowanie()
    status.zakoncz_generowanie(liczba_przetworzonych=10, liczba_bledow=2)

    assert status.w_trakcie is False
    assert status.data_zakonczenia is not None
    assert status.liczba_przetworzonych == 10
    assert status.liczba_bledow == 2
    assert "Zakończono" in status.ostatni_komunikat


@pytest.mark.django_db
def test_status_generowania_aktualizuj_postep():
    """Test aktualizacji postępu"""
    status = StatusGenerowania.get_or_create()
    status.rozpocznij_generowanie()
    status.aktualizuj_postep(5, "Przetworzono 5 autorów")

    assert status.liczba_przetworzonych == 5
    assert status.ostatni_komunikat == "Przetworzono 5 autorów"


@pytest.mark.django_db
def test_status_generowania_czas_trwania():
    """Test obliczania czasu trwania"""
    status = StatusGenerowania.get_or_create()

    # Przed generowaniem
    assert status.czas_trwania is None

    # Ustaw czasy ręcznie dla testu
    start = timezone.now()
    end = start + timezone.timedelta(minutes=5)

    status.data_rozpoczecia = start
    status.data_zakonczenia = end
    status.save()

    assert status.czas_trwania == timezone.timedelta(minutes=5)


@pytest.mark.django_db
def test_metryka_autora_unique_together():
    """Test że para autor-dyscyplina musi być unikalna"""
    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("120.0"),
    )

    # Próba utworzenia drugiej metryki dla tej samej pary powinna się nie udać
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        MetrykaAutora.objects.create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            slot_maksymalny=Decimal("4.0"),
            slot_nazbierany=Decimal("3.0"),
            punkty_nazbierane=Decimal("120.0"),
            slot_wszystkie=Decimal("3.0"),
            punkty_wszystkie=Decimal("120.0"),
        )
