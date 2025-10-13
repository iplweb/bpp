from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from model_bakery import baker

from ewaluacja_common.models import Rodzaj_Autora
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_metryki.models import MetrykaAutora

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Autor_Jednostka,
    Dyscyplina_Naukowa,
    Jednostka,
)


def get_rodzaj_autora(skrot):
    """Helper function to get Rodzaj_Autora object by skrot"""
    return Rodzaj_Autora.objects.get(skrot=skrot)


@pytest.mark.django_db
def test_oblicz_metryki_command_basic(rodzaj_autora_n):
    """Test podstawowego działania komendy oblicz_metryki"""

    # Stwórz dane testowe
    jednostka = baker.make(Jednostka, nazwa="Instytut")
    autor = baker.make(
        Autor, nazwisko="Testowy", imiona="Jan", aktualna_jednostka=jednostka
    )
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")

    # Powiąż autora z jednostką (dla zachowania zgodności z innymi częściami systemu)
    baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )

    # Stwórz ilość udziałów
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Stwórz Autor_Dyscyplina z rodzajem 'N'
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=rodzaj_autora_n,
        rok=2024,
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
        call_command("oblicz_metryki", "--bez-liczby-n", stdout=out)

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
    assert "Znaleziono 1 autorów do przetworzenia" in output
    assert "przetworzono 1" in output.lower()


@pytest.mark.django_db
def test_oblicz_metryki_command_filters(rodzaj_autora_n):
    """Test filtrowania po autorze, dyscyplinie i jednostce"""

    # Stwórz jednostki najpierw
    jednostka1 = baker.make(Jednostka, nazwa="Jednostka1")
    jednostka2 = baker.make(Jednostka, nazwa="Jednostka2")

    # Stwórz dwóch autorów z aktualną jednostką
    autor1 = baker.make(Autor, nazwisko="Autor1", aktualna_jednostka=jednostka1)
    autor2 = baker.make(Autor, nazwisko="Autor2", aktualna_jednostka=jednostka2)

    dyscyplina1 = baker.make(Dyscyplina_Naukowa, nazwa="Dyscyplina1")
    dyscyplina2 = baker.make(Dyscyplina_Naukowa, nazwa="Dyscyplina2")

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
        ilosc_udzialow_monografie=Decimal("1.0"),
    )
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor2,
        dyscyplina_naukowa=dyscyplina2,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Stwórz Autor_Dyscyplina z rodzajem 'N' dla obu autorów
    baker.make(
        Autor_Dyscyplina,
        autor=autor1,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=rodzaj_autora_n,
        rok=2024,
    )
    baker.make(
        Autor_Dyscyplina,
        autor=autor2,
        dyscyplina_naukowa=dyscyplina2,
        rodzaj_autora=rodzaj_autora_n,
        rok=2024,
    )

    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.return_value = (Decimal("100.0"), [1], Decimal("2.5"))

        # Test filtra po autorze
        call_command("oblicz_metryki", "--bez-liczby-n", autor_id=autor1.pk)
        assert MetrykaAutora.objects.filter(autor=autor1).exists()
        assert not MetrykaAutora.objects.filter(autor=autor2).exists()

        MetrykaAutora.objects.all().delete()

        # Test filtra po dyscyplinie
        call_command("oblicz_metryki", "--bez-liczby-n", dyscyplina_id=dyscyplina2.pk)
        assert not MetrykaAutora.objects.filter(dyscyplina_naukowa=dyscyplina1).exists()
        assert MetrykaAutora.objects.filter(dyscyplina_naukowa=dyscyplina2).exists()

        MetrykaAutora.objects.all().delete()

        # Test filtra po jednostce
        call_command("oblicz_metryki", "--bez-liczby-n", jednostka_id=jednostka1.pk)
        assert MetrykaAutora.objects.filter(autor=autor1).exists()
        assert not MetrykaAutora.objects.filter(autor=autor2).exists()


@pytest.mark.django_db
def test_oblicz_metryki_command_error_handling(rodzaj_autora_n):
    """Test obsługi błędów w komendzie"""

    autor = baker.make(Autor, nazwisko="Błędny")
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Stwórz Autor_Dyscyplina z rodzajem 'N'
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=rodzaj_autora_n,
        rok=2024,
    )

    # Mockuj zbieraj_sloty aby rzucił wyjątek
    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.side_effect = Exception("Test error")

        out = StringIO()
        call_command("oblicz_metryki", "--bez-liczby-n", stdout=out)

        output = out.getvalue()

    # Sprawdź że błąd został zaraportowany
    assert "Błąd" in output
    assert "Błędny" in output
    assert "Test error" in output

    # Sprawdź że metryka nie została utworzona
    assert MetrykaAutora.objects.count() == 0


@pytest.mark.django_db
def test_oblicz_metryki_command_parameters(rodzaj_autora_n):
    """Test parametrów rok_min, rok_max i minimalny_pk"""

    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Stwórz Autor_Dyscyplina z rodzajem 'N'
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=rodzaj_autora_n,
        rok=2024,
    )

    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.return_value = (Decimal("100.0"), [1], Decimal("2.5"))

        call_command(
            "oblicz_metryki",
            "--bez-liczby-n",
            rok_min=2020,
            rok_max=2023,
            minimalny_pk=5.0,
        )

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


@pytest.mark.django_db
def test_oblicz_metryki_command_rodzaj_autora_filter(
    rodzaj_autora_n, rodzaj_autora_b, rodzaj_autora_d, rodzaj_autora_z
):
    """Test filtrowania po rodzaju autora"""

    # Stwórz trzech autorów z różnymi rodzajami
    autor_n = baker.make(Autor, nazwisko="Pracownik")
    autor_d = baker.make(Autor, nazwisko="Doktorant")
    autor_b = baker.make(Autor, nazwisko="Badawczy")

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa")

    # Ilości udziałów dla wszystkich trzech
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor_n,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor_d,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor_b,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Autor_Dyscyplina - N, D, B
    baker.make(
        Autor_Dyscyplina,
        autor=autor_n,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=get_rodzaj_autora("N"),
        rok=2024,
    )
    baker.make(
        Autor_Dyscyplina,
        autor=autor_d,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=get_rodzaj_autora("D"),
        rok=2024,
    )
    baker.make(
        Autor_Dyscyplina,
        autor=autor_b,
        dyscyplina_naukowa=dyscyplina,
        rodzaj_autora=get_rodzaj_autora("B"),
        rok=2024,
    )

    with patch.object(Autor, "zbieraj_sloty") as mock_zbieraj:
        mock_zbieraj.return_value = (Decimal("100.0"), [1], Decimal("2.5"))

        # Domyślnie powinno generować dla wszystkich rodzajów (N, D, B, Z, " ")
        out = StringIO()
        call_command("oblicz_metryki", "--bez-liczby-n", stdout=out)

        assert MetrykaAutora.objects.filter(autor=autor_n).exists()
        assert MetrykaAutora.objects.filter(autor=autor_d).exists()
        assert MetrykaAutora.objects.filter(autor=autor_b).exists()
        # Nie powinno być komunikatu o pominiętym autorze
        assert "Pominięto Doktorant" not in out.getvalue()
        assert "Pominięto Pracownik" not in out.getvalue()
        assert "Pominięto Badawczy" not in out.getvalue()

        MetrykaAutora.objects.all().delete()

        # Z opcją --rodzaje-autora N powinno generować tylko dla N
        out = StringIO()
        call_command(
            "oblicz_metryki", "--bez-liczby-n", "--rodzaje-autora", "N", stdout=out
        )

        assert MetrykaAutora.objects.filter(autor=autor_n).exists()
        assert not MetrykaAutora.objects.filter(autor=autor_d).exists()
        assert not MetrykaAutora.objects.filter(autor=autor_b).exists()
        # Powinny być komunikaty o pominiętych autorach
        assert "Pominięto Doktorant" in out.getvalue()
        assert "rodzaj_autora = 'D'" in out.getvalue()
        assert "Pominięto Badawczy" in out.getvalue()
        assert "rodzaj_autora = 'B'" in out.getvalue()

        MetrykaAutora.objects.all().delete()

        # Z opcją --rodzaje-autora B powinno generować tylko dla B
        out = StringIO()
        call_command(
            "oblicz_metryki", "--bez-liczby-n", "--rodzaje-autora", "B", stdout=out
        )

        assert not MetrykaAutora.objects.filter(autor=autor_n).exists()
        assert not MetrykaAutora.objects.filter(autor=autor_d).exists()
        assert MetrykaAutora.objects.filter(autor=autor_b).exists()
        # Powinny być komunikaty o pominiętych autorach
        assert "Pominięto Pracownik" in out.getvalue()
        assert "rodzaj_autora = 'N'" in out.getvalue()
        assert "Pominięto Doktorant" in out.getvalue()
        assert "rodzaj_autora = 'D'" in out.getvalue()
