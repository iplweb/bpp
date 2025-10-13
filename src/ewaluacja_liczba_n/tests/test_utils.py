from decimal import Decimal

import pytest
from model_bakery import baker

from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok, LiczbaNDlaUczelni
from ewaluacja_liczba_n.utils import (
    oblicz_liczby_n_dla_ewaluacji_2022_2025,
    oblicz_srednia_liczbe_n_dla_dyscyplin,
)

from bpp.models import Autor, Autor_Dyscyplina


@pytest.mark.parametrize("zaokraglaj", [True, False])
def test_oblicz_liczby_n_dla_ewaluacji_2022_2025_prosty(
    uczelnia,
    autor_jan_nowak,
    dyscyplina1,
    zaokraglaj,
):
    ad_kwargs = dict(
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=1,
        procent_dyscypliny=100,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
        rok=2022,
    )
    # Musimy utworzyc tu 12 autorow * 5 aby sprawic, ze dyscyplina1 bedzie
    # miała liczbę N większą od 12. W ten sposób nie zostanie usunięta z wykazu
    # dyscyplin raportowanych:
    for _elem in range(12 * 5):
        autor = baker.make(Autor)
        Autor_Dyscyplina.objects.create(autor=autor, **ad_kwargs)

    Autor_Dyscyplina.objects.create(autor=autor_jan_nowak, **ad_kwargs)

    uczelnia.przydzielaj_1_slot_gdy_udzial_mniejszy = zaokraglaj
    uczelnia.save()

    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    assert (
        IloscUdzialowDlaAutoraZaRok.objects.get(autor=autor_jan_nowak).ilosc_udzialow
        == 1
    )

    # Liczba N wyniesie wobec tego 12 autorów * 5 = 60 + 1 autor == 61/4 =
    assert (
        LiczbaNDlaUczelni.objects.get(dyscyplina_naukowa=dyscyplina1).liczba_n == 15.25
    )


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_dla_dyscyplin_podstawowy(uczelnia, dyscyplina1):
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
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
    )

    # Autor 2: pół etatu
    Autor_Dyscyplina.objects.create(
        autor=autor2,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("0.5"),
        procent_dyscypliny=100,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
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
    # Suma udziałów: 2.0 + 1.0 = 3.0
    # Suma etatów: 1.0 + 0.5 = 1.5
    # Średnia na etat: 3.0 / 1.5 = 2.0
    # Liczba lat: 1
    # Wynik: 2.0 * 1 = 2.0
    wynik = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    )
    assert wynik.liczba_n == Decimal("2.50")


@pytest.mark.django_db
def test_oblicz_srednia_liczbe_n_dla_dyscyplin_wieloletni(uczelnia, dyscyplina1):
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
            rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
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
def test_oblicz_srednia_liczbe_n_tylko_pracownicy_n(uczelnia, dyscyplina1):
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
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
    )

    # Autor D (doktorant) - nie powinien być uwzględniony
    Autor_Dyscyplina.objects.create(
        autor=autor_d,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.D,
    )

    # Utwórz udziały dla obu
    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor_n,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
    )

    IloscUdzialowDlaAutoraZaRok.objects.create(
        rok=2022,
        autor=autor_d,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.D,
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
def test_oblicz_srednia_liczbe_n_autor_b_nie_liczony(uczelnia, dyscyplina1):
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
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
    )

    # Autor B (badawczy) - nie powinien być uwzględniony
    Autor_Dyscyplina.objects.create(
        autor=autor_b,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.B,
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
def test_oblicz_srednia_liczbe_n_brak_wymiaru_etatu(uczelnia, dyscyplina1):
    """Test że autorzy bez wymiaru etatu są pomijani."""
    autor = baker.make(Autor)

    # Autor bez wymiaru etatu
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=None,  # Brak wymiaru etatu
        procent_dyscypliny=100,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
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

    # Nie powinno być wyniku, bo autor nie ma wymiaru etatu
    assert not LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina1
    ).exists()
