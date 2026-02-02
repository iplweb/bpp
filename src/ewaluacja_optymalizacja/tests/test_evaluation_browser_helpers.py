"""Testy funkcji pomocniczych przeglądarki ewaluacji.

Ten moduł zawiera testy dla funkcji pomocniczych używanych w widokach przeglądarki
ewaluacji, w tym:
- _get_reported_disciplines
- _snapshot_discipline_points
- _get_discipline_summary
- _get_filter_options
- _get_filtered_publications

Zawiera również fixtures używane przez inne moduły testowe przeglądarki ewaluacji.
"""

import pytest
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from ewaluacja_optymalizacja.models import OptimizationRun
from ewaluacja_optymalizacja.views.evaluation_browser import (
    _get_discipline_summary,
    _get_filter_options,
    _get_filtered_publications,
    _get_reported_disciplines,
    _snapshot_discipline_points,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def uczelnia(db):
    """Utwórz uczelnię testową."""
    return baker.make(Uczelnia, nazwa="Testowa Uczelnia")


@pytest.fixture
def dyscyplina_raportowana(db, uczelnia):
    """Utwórz dyscyplinę raportowaną (liczba_n >= 12)."""
    from ewaluacja_common.models import Rodzaj_Autora
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka", kod="11.1")

    # Utwórz rodzaj autora jeśli nie istnieje
    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "jest_w_n": True, "sort": 1},
    )

    # Utwórz LiczbaNDlaUczelni z liczba_n >= 12
    LiczbaNDlaUczelni.objects.create(
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina,
        liczba_n=15,
    )

    return dyscyplina


@pytest.fixture
def dyscyplina_druga(db):
    """Utwórz drugą dyscyplinę (subdyscyplina)."""
    return baker.make(Dyscyplina_Naukowa, nazwa="Matematyka", kod="11.2")


@pytest.fixture
def autor_z_dyscyplina(db, dyscyplina_raportowana):
    """Utwórz autora z przypisaną dyscypliną."""
    from ewaluacja_common.models import Rodzaj_Autora

    autor = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    jednostka = baker.make("bpp.Jednostka")

    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "jest_w_n": True, "sort": 1},
    )

    # Utwórz Autor_Dyscyplina dla lat 2022-2025
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina_raportowana,
            subdyscyplina_naukowa=None,
            rodzaj_autora=rodzaj_autora,
        )

    return autor, jednostka


@pytest.fixture
def autor_dwudyscyplinowy(db, dyscyplina_raportowana, dyscyplina_druga):
    """Utwórz autora z dwoma dyscyplinami."""
    from ewaluacja_common.models import Rodzaj_Autora

    autor = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    jednostka = baker.make("bpp.Jednostka")

    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "jest_w_n": True, "sort": 1},
    )

    # Utwórz Autor_Dyscyplina z dwoma dyscyplinami
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina_raportowana,
            subdyscyplina_naukowa=dyscyplina_druga,
            rodzaj_autora=rodzaj_autora,
        )

    return autor, jednostka


@pytest.fixture
def publikacja_ciagle(db, autor_z_dyscyplina, dyscyplina_raportowana):
    """Utwórz publikację ciągłą z autorem."""
    autor, jednostka = autor_z_dyscyplina

    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Testowa publikacja ciągła",
    )

    autor_rekord = baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,
        afiliuje=True,
        zatrudniony=True,
        przypieta=True,
    )

    return pub, autor_rekord


@pytest.fixture
def publikacja_zwarta(db, autor_z_dyscyplina, dyscyplina_raportowana):
    """Utwórz publikację zwartą z autorem."""
    autor, jednostka = autor_z_dyscyplina

    pub = baker.make(
        Wydawnictwo_Zwarte,
        rok=2023,
        tytul_oryginalny="Testowa publikacja zwarta",
    )

    autor_rekord = baker.make(
        Wydawnictwo_Zwarte_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,
        afiliuje=True,
        zatrudniony=True,
        przypieta=True,
    )

    return pub, autor_rekord


# =============================================================================
# Testy funkcji _get_reported_disciplines
# =============================================================================


@pytest.mark.django_db
def test_get_reported_disciplines_empty(uczelnia):
    """Test gdy nie ma raportowanych dyscyplin."""
    result = _get_reported_disciplines(uczelnia)
    assert result == []


@pytest.mark.django_db
def test_get_reported_disciplines_with_data(uczelnia, dyscyplina_raportowana):
    """Test pobierania raportowanych dyscyplin."""
    result = _get_reported_disciplines(uczelnia)
    assert dyscyplina_raportowana.pk in result


# =============================================================================
# Testy funkcji _snapshot_discipline_points
# =============================================================================


@pytest.mark.django_db
def test_snapshot_discipline_points_empty(uczelnia):
    """Test snapshotu gdy nie ma OptimizationRun."""
    result = _snapshot_discipline_points(uczelnia)
    assert result == {}


@pytest.mark.django_db
def test_snapshot_discipline_points_with_data(uczelnia, dyscyplina_raportowana):
    """Test snapshotu z danymi OptimizationRun."""
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina_raportowana,
        status="completed",
        total_points=150.5,
    )

    result = _snapshot_discipline_points(uczelnia)
    assert str(dyscyplina_raportowana.pk) in result
    assert result[str(dyscyplina_raportowana.pk)] == 150.5


# =============================================================================
# Testy funkcji _get_discipline_summary
# =============================================================================


@pytest.mark.django_db
def test_get_discipline_summary_empty(uczelnia):
    """Test podsumowania gdy nie ma danych."""
    result = _get_discipline_summary(uczelnia)
    assert result["disciplines"] == []
    assert result["total_points"] == 0


@pytest.mark.django_db
def test_get_discipline_summary_with_diff(uczelnia, dyscyplina_raportowana):
    """Test podsumowania z obliczeniem diff."""
    # Utwórz OptimizationRun
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina_raportowana,
        status="completed",
        total_points=200.0,
    )

    # Punkty przed (było 180)
    punkty_przed = {str(dyscyplina_raportowana.pk): 180.0}

    result = _get_discipline_summary(uczelnia, punkty_przed)

    assert len(result["disciplines"]) == 1
    assert result["disciplines"][0]["punkty"] == 200.0
    assert result["disciplines"][0]["diff"] == 20.0
    assert result["disciplines"][0]["has_diff"] is True
    assert result["total_points"] == 200.0
    assert result["total_diff"] == 20.0


# =============================================================================
# Testy funkcji _get_filter_options
# =============================================================================


@pytest.mark.django_db
def test_get_filter_options(uczelnia, dyscyplina_raportowana):
    """Test pobierania opcji filtrów."""
    result = _get_filter_options(uczelnia)

    assert "dyscypliny" in result
    assert "lata" in result
    assert result["lata"] == [2022, 2023, 2024, 2025]
    assert dyscyplina_raportowana in list(result["dyscypliny"])


# =============================================================================
# Testy funkcji _get_filtered_publications
# =============================================================================


@pytest.mark.django_db
def test_get_filtered_publications_basic(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test podstawowego pobierania publikacji."""
    reported_ids = [dyscyplina_raportowana.pk]
    filters = {}

    result = _get_filtered_publications(uczelnia, filters, reported_ids)

    assert len(result) == 1
    assert result[0]["model_type"] == "ciagle"
    assert result[0]["rok"] == 2023
    assert len(result[0]["authors"]) == 1


@pytest.mark.django_db
def test_get_filtered_publications_by_year(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtrowania po roku."""
    reported_ids = [dyscyplina_raportowana.pk]

    # Filtr na 2023 - powinno zwrócić
    result_2023 = _get_filtered_publications(uczelnia, {"rok": "2023"}, reported_ids)
    assert len(result_2023) == 1

    # Filtr na 2022 - nie powinno zwrócić
    result_2022 = _get_filtered_publications(uczelnia, {"rok": "2022"}, reported_ids)
    assert len(result_2022) == 0


@pytest.mark.django_db
def test_get_filtered_publications_by_title(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtrowania po tytule."""
    reported_ids = [dyscyplina_raportowana.pk]

    # Filtr pasujący
    result = _get_filtered_publications(uczelnia, {"tytul": "Testowa"}, reported_ids)
    assert len(result) == 1

    # Filtr niepasujący
    result_none = _get_filtered_publications(
        uczelnia, {"tytul": "NieIstnieje"}, reported_ids
    )
    assert len(result_none) == 0


@pytest.mark.django_db
def test_get_filtered_publications_by_author(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtrowania po nazwisku autora."""
    reported_ids = [dyscyplina_raportowana.pk]

    # Filtr pasujący
    result = _get_filtered_publications(
        uczelnia, {"nazwisko": "Kowalski"}, reported_ids
    )
    assert len(result) == 1

    # Filtr niepasujący
    result_none = _get_filtered_publications(
        uczelnia, {"nazwisko": "Nieistniejący"}, reported_ids
    )
    assert len(result_none) == 0


@pytest.mark.django_db
def test_get_filtered_publications_by_punkty_range(
    db, uczelnia, dyscyplina_raportowana, autor_z_dyscyplina
):
    """Test filtrowania po zakresie punktów (punkty_od, punkty_do)."""
    from decimal import Decimal

    autor, jednostka = autor_z_dyscyplina
    reported_ids = [dyscyplina_raportowana.pk]

    # Utwórz publikacje z różnymi punktami
    pub1 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja 40 pkt",
        punkty_kbn=Decimal("40.00"),
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub1,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,
        afiliuje=True,
        zatrudniony=True,
    )

    pub2 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja 100 pkt",
        punkty_kbn=Decimal("100.00"),
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub2,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,
        afiliuje=True,
        zatrudniony=True,
    )

    pub3 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja 200 pkt",
        punkty_kbn=Decimal("200.00"),
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub3,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,
        afiliuje=True,
        zatrudniony=True,
    )

    # Filtr tylko punkty_od (>= 100)
    result_od = _get_filtered_publications(uczelnia, {"punkty_od": "100"}, reported_ids)
    assert len(result_od) == 2
    punkty = {p["punkty_kbn"] for p in result_od}
    assert Decimal("100.00") in punkty
    assert Decimal("200.00") in punkty

    # Filtr tylko punkty_do (<= 100)
    result_do = _get_filtered_publications(uczelnia, {"punkty_do": "100"}, reported_ids)
    assert len(result_do) == 2
    punkty = {p["punkty_kbn"] for p in result_do}
    assert Decimal("40.00") in punkty
    assert Decimal("100.00") in punkty

    # Filtr zakres (40-100)
    result_range = _get_filtered_publications(
        uczelnia, {"punkty_od": "40", "punkty_do": "100"}, reported_ids
    )
    assert len(result_range) == 2
    punkty = {p["punkty_kbn"] for p in result_range}
    assert Decimal("40.00") in punkty
    assert Decimal("100.00") in punkty
    assert Decimal("200.00") not in punkty

    # Filtr zakres wykluczający wszystkie (150-180)
    result_empty = _get_filtered_publications(
        uczelnia, {"punkty_od": "150", "punkty_do": "180"}, reported_ids
    )
    assert len(result_empty) == 0

    # Bez filtra punktów - wszystkie publikacje
    result_all = _get_filtered_publications(uczelnia, {}, reported_ids)
    assert len(result_all) == 3
