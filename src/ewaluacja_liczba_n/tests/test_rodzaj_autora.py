from decimal import Decimal

import pytest
from model_bakery import baker

from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
)
from ewaluacja_liczba_n.utils import oblicz_sumy_udzialow_za_calosc

from bpp.models import Autor, Autor_Dyscyplina


@pytest.mark.django_db
def test_oblicz_sumy_udzialow_za_calosc_jeden_rodzaj_autora(
    dyscyplina1, rodzaj_autora_n
):
    """Test komentarza z jednym rodzajem autora przez wszystkie lata."""
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

    # Sprawdź wynik
    wynik = IloscUdzialowDlaAutoraZaCalosc.objects.get(
        autor=autor, dyscyplina_naukowa=dyscyplina1
    )

    # Sprawdź czy komentarz zawiera informacje o rodzaju autora
    assert "Lata z danymi: 2022, 2023, 2024" in wynik.komentarz
    assert f"rodzaj autora: {rodzaj_autora_n.nazwa}" in wynik.komentarz


@pytest.mark.django_db
def test_oblicz_sumy_udzialow_za_calosc_wiele_rodzajow_autora(
    dyscyplina1, rodzaj_autora_n, rodzaj_autora_d
):
    """Test komentarza z wieloma rodzajami autora w różnych latach."""
    autor = baker.make(Autor)

    # Rok 2022 - pracownik naukowy
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Rok 2023 - doktorant
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2023,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_d,
    )

    # Rok 2024 - ponownie pracownik naukowy
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

    # Sprawdź wynik
    wynik = IloscUdzialowDlaAutoraZaCalosc.objects.get(
        autor=autor, dyscyplina_naukowa=dyscyplina1
    )

    # Sprawdź czy komentarz zawiera informacje o różnych rodzajach autora
    assert "Lata z danymi: 2022, 2023, 2024" in wynik.komentarz
    assert (
        "rodzaj autora: 2022 - pracownik naukowy, 2023 - doktorant, 2024 - pracownik naukowy"
        in wynik.komentarz
    )


@pytest.mark.django_db
def test_oblicz_sumy_udzialow_za_calosc_brak_rodzaju_autora(dyscyplina1):
    """Test komentarza gdy autor nie ma przypisanego rodzaju autora."""
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

    # Sprawdź wynik
    wynik = IloscUdzialowDlaAutoraZaCalosc.objects.get(
        autor=autor, dyscyplina_naukowa=dyscyplina1
    )

    # Sprawdź czy komentarz zawiera tylko informacje o latach
    assert "Lata z danymi: 2022, 2023" in wynik.komentarz
    assert "rodzaj autora:" not in wynik.komentarz
