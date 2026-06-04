"""Testy wirtualnego pola DjangoQL ``jednostka_z_podjednostkami__rel``.

Pole dopasowuje rekordy publikacji, których autor jest przypisany do
wybranej jednostki LUB dowolnej jednostki z jej rodziny MPTT (przodkowie +
sama + potomkowie). Odwzorowuje multiseek ``EQUAL_PLUS_SUB_FEMALE``:
``Q(autorzy__jednostka__in=value.get_family())``.
"""

import pytest
from djangoql.queryset import apply_search

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_jednostka_z_podjednostkami_in_schema():
    from bpp.djangoql_schema import BppQLSchema
    from bpp.models import Rekord

    schema = BppQLSchema(Rekord)
    fields = schema.models[BppQLSchema.model_label(Rekord)]
    assert "jednostka_z_podjednostkami__rel" in fields


@pytest.mark.django_db
def test_jednostka_z_podjednostkami_matches_subunit_author(
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    jednostka,
    jednostka_podrzedna,
):
    from denorm import denorms

    from bpp.djangoql_schema import BppQLSchema
    from bpp.models import Rekord

    # Autor przypisany do JEDNOSTKI PODRZĘDNEJ (dziecko ``jednostka``).
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka_podrzedna)
    denorms.flush()

    # Zapytanie po JEDNOSTCE NADRZĘDNEJ powinno znaleźć publikację autora
    # z podjednostki dzięki rozwinięciu rodziny MPTT.
    query = f'jednostka_z_podjednostkami__rel = "Parent [{jednostka.pk}]"'
    found = apply_search(Rekord.objects.all(), query, schema=BppQLSchema).distinct()

    assert found.count() == 1
    assert found.first().tytul_oryginalny == wydawnictwo_ciagle.tytul_oryginalny
