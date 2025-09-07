from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from model_bakery import baker

from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_metryki.models import MetrykaAutora

from bpp.models import Autor, Autor_Jednostka, Dyscyplina_Naukowa, Jednostka


@pytest.mark.django_db
def test_oblicz_metryki_command_basic():
    """Test podstawowego działania komendy oblicz_metryki"""

    # Stwórz dane testowe
    autor = baker.make(Autor, nazwisko="Testowy", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")
    jednostka = baker.make(Jednostka, nazwa="Instytut")

    # Powiąż autora z jednostką
    baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )

    # Stwórz ilość udziałów
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
    )

    # Mockuj metodę zbieraj_sloty
    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        # Zwróć różne wartości dla różnych wywołań
        mock_zbieraj.side_effect = [
            (Decimal("140.0"), [1, 2, 3], Decimal("3.5")),  # algorytm plecakowy
            (Decimal("150.0"), [1, 2, 3, 4, 5], Decimal("4.0")),  # wszystkie prace
        ]

        # Wywołaj komendę
        out = StringIO()
        call_command("oblicz_metryki", stdout=out)

        output = out.getvalue()

    # Sprawdź że metryka została utworzona
    assert MetrykaAutora.objects.count() == 1

    metryka = MetrykaAutora.objects.first()
    assert metryka.autor == autor
    assert metryka.dyscyplina_naukowa == dyscyplina
    assert metryka.jednostka == jednostka
    assert metryka.slot_maksymalny == Decimal("4.0")
    assert metryka.slot_nazbierany == Decimal("3.5")
    assert metryka.punkty_nazbierane == Decimal("140.0")
    assert metryka.prace_nazbierane == [1, 2, 3]
    assert metryka.slot_wszystkie == Decimal("4.0")
    assert metryka.punkty_wszystkie == Decimal("150.0")
    assert metryka.prace_wszystkie == [1, 2, 3, 4, 5]
    assert metryka.liczba_prac_wszystkie == 5

    # Sprawdź output
    assert "Testowy" in output
    assert "utworzono" in output.lower()


@pytest.mark.django_db
def test_oblicz_metryki_command_nadpisz():
    """Test nadpisywania istniejących metryk"""

    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    # Stwórz istniejącą metrykę
    old_metryka = baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        slot_maksymalny=Decimal("3.0"),
        slot_nazbierany=Decimal("2.0"),
        punkty_nazbierane=Decimal("80.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("90.0"),
    )

    # Stwórz ilość udziałów
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
    )

    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.side_effect = [
            (Decimal("160.0"), [1, 2, 3, 4], Decimal("4.0")),
            (Decimal("160.0"), [1, 2, 3, 4], Decimal("4.0")),
        ]

        # Wywołaj bez nadpisywania - powinno pominąć
        out = StringIO()
        call_command("oblicz_metryki", nadpisz=False, stdout=out)

        # Sprawdź że metryka nie została zmieniona
        old_metryka.refresh_from_db()
        assert old_metryka.punkty_nazbierane == Decimal("80.0")
        assert "pominięto" in out.getvalue().lower()

        # Wywołaj z nadpisywaniem
        out = StringIO()
        call_command("oblicz_metryki", nadpisz=True, stdout=out)

        # Sprawdź że metryka została zaktualizowana
        old_metryka.refresh_from_db()
        assert old_metryka.punkty_nazbierane == Decimal("160.0")
        assert "zaktualizowano" in out.getvalue().lower()


@pytest.mark.django_db
def test_oblicz_metryki_command_filters():
    """Test filtrowania po autorze, dyscyplinie i jednostce"""

    # Stwórz dwóch autorów
    autor1 = baker.make(Autor, nazwisko="Autor1")
    autor2 = baker.make(Autor, nazwisko="Autor2")

    dyscyplina1 = baker.make(Dyscyplina_Naukowa, nazwa="Dyscyplina1")
    dyscyplina2 = baker.make(Dyscyplina_Naukowa, nazwa="Dyscyplina2")

    jednostka1 = baker.make(Jednostka, nazwa="Jednostka1")
    jednostka2 = baker.make(Jednostka, nazwa="Jednostka2")

    # Powiązania
    baker.make(
        Autor_Jednostka,
        autor=autor1,
        jednostka=jednostka1,
        podstawowe_miejsce_pracy=True,
    )
    baker.make(
        Autor_Jednostka,
        autor=autor2,
        jednostka=jednostka2,
        podstawowe_miejsce_pracy=True,
    )

    # Ilości udziałów
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor1,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("4.0"),
    )
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor2,
        dyscyplina_naukowa=dyscyplina2,
        ilosc_udzialow=Decimal("4.0"),
    )

    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.return_value = (Decimal("100.0"), [1], Decimal("2.5"))

        # Test filtra po autorze
        call_command("oblicz_metryki", autor_id=autor1.pk)
        assert MetrykaAutora.objects.filter(autor=autor1).exists()
        assert not MetrykaAutora.objects.filter(autor=autor2).exists()

        MetrykaAutora.objects.all().delete()

        # Test filtra po dyscyplinie
        call_command("oblicz_metryki", dyscyplina_id=dyscyplina2.pk)
        assert not MetrykaAutora.objects.filter(dyscyplina_naukowa=dyscyplina1).exists()
        assert MetrykaAutora.objects.filter(dyscyplina_naukowa=dyscyplina2).exists()

        MetrykaAutora.objects.all().delete()

        # Test filtra po jednostce
        call_command("oblicz_metryki", jednostka_id=jednostka1.pk)
        assert MetrykaAutora.objects.filter(autor=autor1).exists()
        assert not MetrykaAutora.objects.filter(autor=autor2).exists()


@pytest.mark.django_db
def test_oblicz_metryki_command_error_handling():
    """Test obsługi błędów w komendzie"""

    autor = baker.make(Autor, nazwisko="Błędny")
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
    )

    # Mockuj zbieraj_sloty aby rzucił wyjątek
    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.side_effect = Exception("Test error")

        out = StringIO()
        call_command("oblicz_metryki", stdout=out)

        output = out.getvalue()

    # Sprawdź że błąd został zaraportowany
    assert "Błąd" in output
    assert "Błędny" in output
    assert "Test error" in output

    # Sprawdź że metryka nie została utworzona
    assert MetrykaAutora.objects.count() == 0


@pytest.mark.django_db
def test_oblicz_metryki_command_parameters():
    """Test parametrów rok_min, rok_max i minimalny_pk"""

    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
    )

    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.return_value = (Decimal("100.0"), [1], Decimal("2.5"))

        call_command("oblicz_metryki", rok_min=2020, rok_max=2023, minimalny_pk=5.0)

        # Sprawdź że parametry zostały przekazane do zbieraj_sloty
        calls = mock_zbieraj.call_args_list

        # Pierwsze wywołanie (algorytm plecakowy)
        assert calls[0][1]["rok_min"] == 2020
        assert calls[0][1]["rok_max"] == 2023
        assert calls[0][1]["minimalny_pk"] == Decimal("5.0")
        assert calls[0][1]["dyscyplina_id"] == dyscyplina.pk

        # Drugie wywołanie (wszystkie prace)
        assert calls[1][1]["akcja"] == "wszystko"

    # Sprawdź że metryka zapisała parametry
    metryka = MetrykaAutora.objects.first()
    assert metryka.rok_min == 2020
    assert metryka.rok_max == 2023
