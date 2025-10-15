from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
)
from ewaluacja_liczba_n.utils import oblicz_sumy_udzialow_za_calosc


@pytest.mark.django_db
def test_oblicz_sumy_udzialow_za_calosc_jeden_rodzaj_autora(
    dyscyplina1, rodzaj_autora_n
):
    """Test tworzenia wpisu dla jednego rodzaju autora przez wszystkie lata."""
    autor = baker.make(Autor)

    # Utwórz Autor_Dyscyplina dla tego samego rodzaju autora przez 3 lata
    for rok in [2022, 2023, 2024]:
        Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=Decimal("1.0"),
            procent_dyscypliny=100,
            rodzaj_autora=rodzaj_autora_n,
        )

        # Utwórz udziały dla każdego roku
        IloscUdzialowDlaAutoraZaRok.objects.create(
            rok=rok,
            autor=autor,
            dyscyplina_naukowa=dyscyplina1,
            ilosc_udzialow=Decimal("1.0"),
            ilosc_udzialow_monografie=Decimal("0.5"),
        )

    # Oblicz sumy za cały okres
    oblicz_sumy_udzialow_za_calosc(2022, 2025)

    # Sprawdź wynik - powinien być jeden wpis dla rodzaju N
    wynik = IloscUdzialowDlaAutoraZaCalosc.objects.get(
        autor=autor, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_n
    )

    # Sprawdź wartości
    assert wynik.ilosc_udzialow == Decimal("3.0")
    assert wynik.ilosc_udzialow_monografie == Decimal("1.5")
    assert wynik.rodzaj_autora == rodzaj_autora_n
    # Sprawdź czy komentarz zawiera lata (bez rodzaju autora)
    assert "Lata z danymi: 2022, 2023, 2024" in wynik.komentarz
    # Komentarz NIE powinien zawierać informacji o rodzaju autora
    assert "rodzaj autora:" not in wynik.komentarz


@pytest.mark.django_db
def test_oblicz_sumy_udzialow_za_calosc_wiele_rodzajow_autora(
    dyscyplina1, rodzaj_autora_n, rodzaj_autora_d
):
    """Test tworzenia oddzielnych wpisów dla różnych rodzajów autora."""
    autor = baker.make(Autor)

    # Rok 2022 - pracownik naukowy (N)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Rok 2023 - doktorant (D)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2023,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_d,
    )

    # Rok 2024 - ponownie pracownik naukowy (N)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Utwórz udziały dla każdego roku
    for rok in [2022, 2023, 2024]:
        IloscUdzialowDlaAutoraZaRok.objects.create(
            rok=rok,
            autor=autor,
            dyscyplina_naukowa=dyscyplina1,
            ilosc_udzialow=Decimal("1.0"),
            ilosc_udzialow_monografie=Decimal("0.5"),
        )

    # Oblicz sumy za cały okres
    oblicz_sumy_udzialow_za_calosc(2022, 2025)

    # Sprawdź że są 2 osobne wpisy: jeden dla N, jeden dla D
    assert IloscUdzialowDlaAutoraZaCalosc.objects.count() == 2

    # Sprawdź wpis dla rodzaju N (2022, 2024)
    wynik_n = IloscUdzialowDlaAutoraZaCalosc.objects.get(
        autor=autor, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_n
    )
    assert wynik_n.ilosc_udzialow == Decimal("2.0")  # 2022 + 2024
    assert wynik_n.ilosc_udzialow_monografie == Decimal("1.0")  # 2 * 0.5
    assert "Lata z danymi: 2022, 2024" in wynik_n.komentarz
    assert "rodzaj autora:" not in wynik_n.komentarz

    # Sprawdź wpis dla rodzaju D (2023)
    wynik_d = IloscUdzialowDlaAutoraZaCalosc.objects.get(
        autor=autor, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_d
    )
    assert wynik_d.ilosc_udzialow == Decimal("1.0")  # tylko 2023
    assert wynik_d.ilosc_udzialow_monografie == Decimal(
        "1.00"
    )  # 0.5 zaokrąglone do 1.0
    assert "Lata z danymi: 2023" in wynik_d.komentarz
    assert "rodzaj autora:" not in wynik_d.komentarz
    # Sprawdź czy komentarz zawiera informację o zaokrągleniu
    assert "zaokrąglona: 0.5000 → 1.00" in wynik_d.komentarz


@pytest.mark.django_db
def test_oblicz_sumy_udzialow_za_calosc_brak_rodzaju_autora(dyscyplina1):
    """Test pomijania autorów bez przypisanego rodzaju autora."""
    autor = baker.make(Autor)

    # Utwórz Autor_Dyscyplina bez rodzaju autora
    for rok in [2022, 2023]:
        Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=Decimal("1.0"),
            procent_dyscypliny=100,
            rodzaj_autora=None,  # Brak rodzaju autora
        )

        # Utwórz udziały dla każdego roku
        IloscUdzialowDlaAutoraZaRok.objects.create(
            rok=rok,
            autor=autor,
            dyscyplina_naukowa=dyscyplina1,
            ilosc_udzialow=Decimal("1.0"),
            ilosc_udzialow_monografie=Decimal("0.5"),
        )

    # Oblicz sumy za cały okres
    oblicz_sumy_udzialow_za_calosc(2022, 2025)

    # Sprawdź że NIE został utworzony żaden wpis (rekordy z rodzaj_autora=None są pomijane)
    assert IloscUdzialowDlaAutoraZaCalosc.objects.count() == 0
