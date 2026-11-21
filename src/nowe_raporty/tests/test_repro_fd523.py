"""FD#523: źródło danych z ``charakter_formalny__rel`` nie przechodziło walidacji.

``<pole>__rel`` to picker ze schematu DjangoQL BPP (wyszukiwanie zapytaniem,
adminy). Źródła danych ``flexible_reports`` używały domyślnego schematu
djangoql, który tej notacji nie zna.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from flexible_reports.models import Datasource
from flexible_reports.query_backends import DJANGOQL, DSL, get_backend
from model_bakery import baker

from bpp.models import Charakter_Formalny, Wydawnictwo_Ciagle
from bpp.models.cache import Rekord


def _ds(query, jezyk=DJANGOQL, model=Rekord):
    return Datasource(
        label="x",
        base_model=ContentType.objects.get_for_model(model),
        query_language=jezyk,
        dsl_query=query,
    )


@pytest.mark.django_db
def test_fd523_charakter_formalny_rel_przechodzi_walidacje():
    cf = Charakter_Formalny.objects.first() or baker.make(Charakter_Formalny)
    _ds(f'charakter_formalny__rel = "{cf.nazwa} [{cf.pk}]"').clean()


@pytest.mark.django_db
def test_fd523_charakter_formalny_rel_filtruje(
    wydawnictwo_ciagle, wydawnictwo_zwarte
):
    cf = wydawnictwo_ciagle.charakter_formalny
    ds = _ds(f'charakter_formalny__rel = "{cf.nazwa} [{cf.pk}]"')
    ds.clean()

    wynik = ds.filter_queryset(Rekord.objects.all())

    assert wynik.filter(
        tytul_oryginalny=wydawnictwo_ciagle.tytul_oryginalny
    ).exists()
    assert set(wynik.values_list("charakter_formalny_id", flat=True)) == {cf.pk}


@pytest.mark.django_db
def test_fd523_rel_na_innym_modelu_bazowym():
    cf = Charakter_Formalny.objects.first() or baker.make(Charakter_Formalny)
    _ds(
        f'charakter_formalny__rel = "{cf.nazwa} [{cf.pk}]"',
        model=Wydawnictwo_Ciagle,
    ).clean()


@pytest.mark.django_db
def test_fd523_zwykle_zapytania_djangoql_dzialaja_dalej():
    _ds('charakter_formalny.skrot = "AC" and rok >= 2020').clean()


@pytest.mark.django_db
def test_fd523_nieznane_pole_djangoql_ma_nazwe_i_podpowiedz():
    with pytest.raises(ValidationError) as e:
        _ds('charakter_formalny__skrot = "AC"').clean()
    tekst = " ".join(e.value.messages)
    assert "charakter_formalny__skrot" in tekst
    assert "charakter_formalny.skrot" in tekst


@pytest.mark.django_db
def test_fd523_skladnia_djangoql_w_dsl_daje_podpowiedz():
    with pytest.raises(ValidationError) as e:
        _ds('charakter_formalny__rel = "Artykuł [1]"', jezyk=DSL).clean()
    tekst = " ".join(e.value.messages)
    assert "Unsupported lookup 'rel'" in tekst
    assert "DjangoQL" in tekst


@pytest.mark.django_db
def test_fd523_dsl_bez_podpowiedzi_gdy_to_nie_skladnia_djangoql():
    with pytest.raises(ValidationError) as e:
        # kropka tylko w wartości i w tagu szablonu - to nie składnia DjangoQL
        _ds(
            'nie_ma_takiego_pola = "a.b" AND rok = {{ obiekt.pk }}', jezyk=DSL
        ).clean()
    assert "DjangoQL" not in " ".join(e.value.messages)


@pytest.mark.django_db
def test_fd523_dsl_poprawne_zapytanie_dalej_dziala():
    _ds('charakter_formalny__skrot = "AC" AND rok >= 2020', jezyk=DSL).clean()


def test_fd523_backendy_zainstalowane():
    from nowe_raporty.query_backends import (
        BppDjangoQLQueryBackend,
        BppDSLQueryBackend,
    )

    assert isinstance(get_backend(DJANGOQL), BppDjangoQLQueryBackend)
    assert isinstance(get_backend(DSL), BppDSLQueryBackend)
