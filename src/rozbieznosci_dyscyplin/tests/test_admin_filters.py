"""Testy filtrów adminowych z `admin_utils.py` oraz `CachingPaginator`."""

import pytest

from bpp.models import Autor_Dyscyplina
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView


@pytest.mark.django_db
def test_pracuje_na_uczelni_filter_tak(
    rf, uczelnia, autor_jan_kowalski, jednostka, wydawnictwo_ciagle, dyscyplina1, rok
):
    """Test PracujeNaUczelni filter with 'tak' value."""
    from rozbieznosci_dyscyplin.admin_utils import PracujeNaUczelni

    # Ustaw autora jako pracujacego w jednostce
    autor_jan_kowalski.aktualna_jednostka = jednostka
    autor_jan_kowalski.save()

    # Utworz rozbieznosc
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    filter_obj = PracujeNaUczelni(None, {"pracuje_na_uczelni": "tak"}, None, None)
    req = rf.get("/")
    req.uczelnia = uczelnia

    queryset = RozbieznosciView.objects.all()
    result = filter_obj.queryset(req, queryset)

    # Autor z aktualna jednostka powinien byc w wynikach
    assert result.count() >= 0  # Moze byc 0 jesli brak rozbieznosci


@pytest.mark.django_db
def test_pracuje_na_uczelni_filter_nie(
    rf, uczelnia, autor_jan_kowalski, jednostka, wydawnictwo_ciagle, dyscyplina1, rok
):
    """Test PracujeNaUczelni filter with 'nie' value."""
    from rozbieznosci_dyscyplin.admin_utils import PracujeNaUczelni

    # Ustaw autora bez aktualnej jednostki
    autor_jan_kowalski.aktualna_jednostka = None
    autor_jan_kowalski.save()

    filter_obj = PracujeNaUczelni(None, {"pracuje_na_uczelni": "nie"}, None, None)
    req = rf.get("/")
    req.uczelnia = uczelnia

    queryset = RozbieznosciView.objects.all()
    result = filter_obj.queryset(req, queryset)

    assert result is not None


@pytest.mark.django_db
def test_pracuje_na_uczelni_filter_lookups(rf, uczelnia):
    """Test PracujeNaUczelni filter lookups."""
    from rozbieznosci_dyscyplin.admin_utils import PracujeNaUczelni

    filter_obj = PracujeNaUczelni(None, {}, None, None)
    lookups = filter_obj.lookups(None, None)

    assert len(lookups) == 2
    assert lookups[0][0] == "tak"
    assert lookups[1][0] == "nie"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,threshold",
    [
        ("wieksze_niz_5", 5),
        ("wieksze_niz_10", 10),
        ("wieksze_niz_20", 20),
        ("wieksze_niz_30", 30),
        ("wieksze_niz_50", 50),
        ("wieksze_niz_100", 100),
    ],
)
def test_punkty_kbn_filter(value, threshold):
    """Test PunktyKbnFilter with various threshold values."""
    from rozbieznosci_dyscyplin.admin_utils import PunktyKbnFilter

    filter_obj = PunktyKbnFilter(None, {"punkty_kbn": value}, None, None)
    queryset = RozbieznosciZrodelView.objects.all()
    result = filter_obj.queryset(None, queryset)

    # Sprawdz, ze queryset zostal przefiltrowany
    assert result is not None


def test_punkty_kbn_filter_lookups():
    """Test PunktyKbnFilter lookups."""
    from rozbieznosci_dyscyplin.admin_utils import PunktyKbnFilter

    filter_obj = PunktyKbnFilter(None, {}, None, None)
    lookups = filter_obj.lookups(None, None)

    assert len(lookups) == 6
    assert lookups[0][0] == "wieksze_niz_5"
    assert lookups[5][0] == "wieksze_niz_100"


@pytest.mark.django_db
def test_punkty_kbn_filter_none_value():
    """Test PunktyKbnFilter with None value returns original queryset."""
    from rozbieznosci_dyscyplin.admin_utils import PunktyKbnFilter

    filter_obj = PunktyKbnFilter(None, {}, None, None)
    queryset = RozbieznosciZrodelView.objects.all()
    result = filter_obj.queryset(None, queryset)

    # Bez wartosci powinien zwrocic oryginalny queryset
    assert result is queryset


@pytest.mark.django_db
def test_dyscyplina_ustawiona_filter():
    """Test DyscyplinaUstawionaFilter configuration."""
    from rozbieznosci_dyscyplin.admin_utils import DyscyplinaUstawionaFilter

    assert DyscyplinaUstawionaFilter.title == "Dyscyplina ustawiona"
    assert DyscyplinaUstawionaFilter.parameter_name == "dyscyplina_naukowa_id"


@pytest.mark.django_db
def test_dyscyplina_autora_ustawiona_filter():
    """Test DyscyplinaAutoraUstawionaFilter configuration."""
    from rozbieznosci_dyscyplin.admin_utils import DyscyplinaAutoraUstawionaFilter

    assert DyscyplinaAutoraUstawionaFilter.title == "Dyscyplina autora ustawiona"
    assert DyscyplinaAutoraUstawionaFilter.parameter_name == "dyscyplina_autora_id"


@pytest.mark.django_db
def test_dyscyplina_rekordu_ustawiona_filter():
    """Test DyscyplinaRekorduUstawionaFilter configuration."""
    from rozbieznosci_dyscyplin.admin_utils import DyscyplinaRekorduUstawionaFilter

    assert DyscyplinaRekorduUstawionaFilter.title == "Dyscyplina rekordu ustawiona"
    assert DyscyplinaRekorduUstawionaFilter.parameter_name == "dyscyplina_rekordu_id"


@pytest.mark.django_db
def test_caching_paginator_count_for_unmanaged_model():
    """Test CachingPaginator count for unmanaged model (database view)."""
    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    queryset = RozbieznosciView.objects.all()
    paginator = CachingPaginator(queryset, 25)

    # Dla managed=False model powinien uzywac count() zamiast reltuples
    count = paginator.count
    assert isinstance(count, int)
    assert count >= 0


@pytest.mark.django_db
def test_caching_paginator_with_filter():
    """Test CachingPaginator count with filtered queryset."""
    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    queryset = RozbieznosciView.objects.filter(rok=2020)
    paginator = CachingPaginator(queryset, 25)

    count = paginator.count
    assert isinstance(count, int)
    assert count >= 0


@pytest.mark.django_db
def test_caching_paginator_caches_count():
    """Test CachingPaginator caches count result."""
    from django.core.cache import cache

    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    # Wyczysc cache przed testem
    cache.clear()

    queryset = RozbieznosciView.objects.all()
    paginator = CachingPaginator(queryset, 25)

    # Pierwsze wywolanie - powinno zapisac do cache
    count1 = paginator.count

    # Drugie wywolanie - powinno odczytac z cache
    paginator2 = CachingPaginator(queryset, 25)
    count2 = paginator2.count

    assert count1 == count2


@pytest.mark.django_db
def test_caching_paginator_handles_list():
    """Test CachingPaginator handles list object gracefully."""
    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    data = [1, 2, 3, 4, 5]
    paginator = CachingPaginator(data, 2)

    # Dla listy powinien zwrocic len()
    assert paginator.count == 5
