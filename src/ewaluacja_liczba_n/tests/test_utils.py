from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaRok,
    LiczbaNDlaUczelni,
)
from ewaluacja_liczba_n.utils import (
    oblicz_liczby_n_dla_ewaluacji_2022_2025,
    oblicz_srednia_liczbe_n_dla_dyscyplin,
)


@pytest.mark.parametrize("zaokraglaj", [True, False])
def test_oblicz_liczby_n_dla_ewaluacji_2022_2025_prosty(
    uczelnia,
    autor_jan_nowak,
    dyscyplina1,
    zaokraglaj,
    rodzaj_autora_n,
):
    # Musimy utworzyc tu 12 autorow * 5 aby sprawic, ze dyscyplina1 bedzie
    # miała liczbę N większą od 12. W ten sposób nie zostanie usunięta z wykazu
    # dyscyplin raportowanych.
    # WAŻNE: Tworzymy dane dla roku 2022 i 2025, aby dyscyplina miała N >= 12 na koniec 2025
    for rok in [2022, 2025]:
        ad_kwargs = dict(
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=1,
            procent_dyscypliny=100,
            rodzaj_autora=rodzaj_autora_n,
            rok=rok,
        )
        for _elem in range(12 * 5):
            autor = baker.make(Autor)
            Autor_Dyscyplina.objects.create(autor=autor, **ad_kwargs)

    # Dodaj autor_jan_nowak tylko dla roku 2022
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=1,
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
        rok=2022,
    )

    uczelnia.przydzielaj_1_slot_gdy_udzial_mniejszy = zaokraglaj
    uczelnia.save()

    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    assert (
        IloscUdzialowDlaAutoraZaRok.objects.get(autor=autor_jan_nowak).ilosc_udzialow
        == 1
    )

    # Liczba N:
    # - 2022: 60 autorów + Jan Nowak = 61
    # - 2025: 60 autorów (bez Jana Nowaka)
    # Średnia: (61 + 60) / 4 lata = 30.25
    assert (
        LiczbaNDlaUczelni.objects.get(dyscyplina_naukowa=dyscyplina1).liczba_n == 30.25
    )


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_dla_dyscyplin_podstawowy(
    uczelnia, dyscyplina1, rodzaj_autora_n
):
    """Test podstawowej funkcjonalności obliczania średniej liczby N."""
    # Utwórz autorów z różnymi wymiarami etatu
    autor1 = baker.make(Autor)
    autor2 = baker.make(Autor)

    # Autor 1: pełny etat
    Autor_Dyscyplina.objects.create(
        autor=autor1,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Autor 2: pół etatu
    Autor_Dyscyplina.objects.create(
        autor=autor2,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("0.5"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Utwórz udziały
    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor1,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor2,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
    )

    # Oblicz średnią
    oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, 2022, 2022)

    # Sprawdź wynik
    # NIEWAŻONA suma udziałów: 2.0 + 1.0 = 3.0
    # Liczba lat: 1
    # Wynik: 3.0 / 1 = 3.0
    wynik = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    )
    assert wynik.liczba_n == Decimal("3.00")


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_dla_dyscyplin_wieloletni(
    uczelnia, dyscyplina1, rodzaj_autora_n
):
    """Test obliczania średniej dla wielu lat."""
    autor = baker.make(Autor)

    # Utwórz dane dla 4 lat (2022-2025)
    for rok in range(2022, 2026):
        Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=Decimal("1.0"),
            procent_dyscypliny=100,
            rodzaj_autora=rodzaj_autora_n,
        )

        IloscUdzialowDlaAutoraZaRok.objects.create(
            rok=rok,
            autor=autor,
            dyscyplina_naukowa=dyscyplina1,
            ilosc_udzialow=Decimal("1.0"),
            ilosc_udzialow_monografie=Decimal("0.5"),
        )

    # Oblicz średnią
    oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, 2022, 2025)

    # Sprawdź wynik
    # Suma udziałów: 4 * 1.0 = 4.0
    # Suma etatów: 4 * 1.0 = 4.0
    # Średnia na etat: 4.0 / 4.0 = 1.0
    # Liczba lat: 4
    # Wynik: 1.0 * 4 = 4.0
    wynik = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    )
    assert wynik.liczba_n == Decimal("1.0")


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_tylko_pracownicy_n(
    uczelnia, dyscyplina1, rodzaj_autora_n, rodzaj_autora_d
):
    """Test że tylko pracownicy typu N są uwzględniani."""
    autor_n = baker.make(Autor)
    autor_d = baker.make(Autor)

    # Autor N - powinien być uwzględniony
    Autor_Dyscyplina.objects.create(
        autor=autor_n,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Autor D (doktorant) - nie powinien być uwzględniony
    Autor_Dyscyplina.objects.create(
        autor=autor_d,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_d,
    )

    # Utwórz udziały dla obu
    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor_n,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor_d,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Oblicz średnią
    oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, 2022, 2022)

    # Sprawdź wynik - tylko autor N powinien być uwzględniony
    wynik = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    )
    # Tylko autor N: 2.0 / 1.0 * 1 = 2.0
    assert wynik.liczba_n == Decimal("2.0")


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_autor_b_nie_liczony(
    uczelnia, dyscyplina1, rodzaj_autora_n, rodzaj_autora_b
):
    """Test że autorzy typu B (badawczy) nie są wliczani do liczby N."""
    autor_n = baker.make(Autor)
    autor_b = baker.make(Autor)

    # Autor N (naukowiec) - powinien być uwzględniony
    Autor_Dyscyplina.objects.create(
        autor=autor_n,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Autor B (badawczy) - nie powinien być uwzględniony
    Autor_Dyscyplina.objects.create(
        autor=autor_b,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_b,
    )

    # Utwórz udziały dla obu
    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor_n,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor_b,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Oblicz średnią
    oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, 2022, 2022)

    # Sprawdź wynik - tylko autor N powinien być uwzględniony
    wynik = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    )
    # Tylko autor N: 2.0 / 1.0 * 1 = 2.0
    assert wynik.liczba_n == Decimal("2.0")


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_brak_wymiaru_etatu(
    uczelnia, dyscyplina1, rodzaj_autora_n
):
    """Test że wymiar etatu nie jest brany pod uwagę przy obliczaniu nieważonej średniej."""
    autor = baker.make(Autor)

    # Autor bez wymiaru etatu
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=None,  # Brak wymiaru etatu
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Utwórz udział
    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
    )

    # Oblicz średnią
    oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, 2022, 2022)

    # Powinien być wynik 2.0, bo liczymy nieważoną sumę udziałów
    wynik = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    )
    assert wynik.liczba_n == Decimal("2.00")


@pytest.mark.django_db
def test_autor_typu_z_ma_udzialy_zero(uczelnia, dyscyplina1, rodzaj_autora_z):
    """
    Test że autor typu Z (licz_sloty=False) ma udziały = 0.0 ale jest widoczny w tabelach.
    """
    autor = baker.make(Autor)

    # Autor typu Z w roku 2025
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2025,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_z,  # Typ Z - licz_sloty=False
    )

    # Uruchom obliczenia
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    # Sprawdź że autor ma wpis w IloscUdzialowDlaAutoraZaRok
    assert IloscUdzialowDlaAutoraZaRok.objects.filter(autor=autor, rok=2025).exists()

    # Sprawdź że udziały = 0.0
    udzial = IloscUdzialowDlaAutoraZaRok.objects.get(autor=autor, rok=2025)
    assert udzial.ilosc_udzialow == Decimal("0.0")
    assert udzial.ilosc_udzialow_monografie == Decimal("0.0")


@pytest.mark.django_db
def test_autor_typu_z_nie_wliczany_do_liczby_n(
    uczelnia, dyscyplina1, rodzaj_autora_n, rodzaj_autora_z
):
    """
    Test że autorzy typu Z nie są wliczani do liczby N, mimo że są widoczni w listach.
    """
    # 15 autorów typu N
    for _i in range(15):
        autor = baker.make(Autor)
        Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=2025,
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=Decimal("1.0"),
            procent_dyscypliny=100,
            rodzaj_autora=rodzaj_autora_n,
        )

    # 10 autorów typu Z (nie powinni być wliczani do N)
    for _i in range(10):
        autor = baker.make(Autor)
        Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=2025,
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=Decimal("1.0"),
            procent_dyscypliny=100,
            rodzaj_autora=rodzaj_autora_z,  # Typ Z
        )

    # Uruchom obliczenia
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    # Sprawdź że wszystkie 25 autorów ma wpisy
    assert IloscUdzialowDlaAutoraZaRok.objects.filter(rok=2025).count() == 25

    # Sprawdź że liczba N = 15 (tylko autorzy typu N)
    from ewaluacja_liczba_n.utils import oblicz_liczbe_n_na_koniec_2025

    liczby_n_2025 = oblicz_liczbe_n_na_koniec_2025(uczelnia)
    assert liczby_n_2025.get(dyscyplina1.id, 0) == Decimal("15.0")


@pytest.mark.django_db
def test_autor_zmienia_typ_z_n_na_z(
    uczelnia, dyscyplina1, rodzaj_autora_n, rodzaj_autora_z
):
    """
    Test że jeśli autor zmienia typ z N na Z, to ma różne udziały w różnych latach.
    """
    autor = baker.make(Autor)

    # Rok 2024: autor typu N
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Rok 2025: ten sam autor ale typ Z
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2025,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_z,
    )

    # Uruchom obliczenia
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    # Sprawdź że w 2024 ma udziały > 0
    udzial_2024 = IloscUdzialowDlaAutoraZaRok.objects.get(autor=autor, rok=2024)
    assert udzial_2024.ilosc_udzialow == Decimal("1.0")

    # Sprawdź że w 2025 ma udziały = 0
    udzial_2025 = IloscUdzialowDlaAutoraZaRok.objects.get(autor=autor, rok=2025)
    assert udzial_2025.ilosc_udzialow == Decimal("0.0")
