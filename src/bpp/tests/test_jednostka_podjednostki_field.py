"""Testy wirtualnego pola DjangoQL ``jednostka_z_podjednostkami__rel``.

Pole dopasowuje rekordy publikacji, których autor jest przypisany do
wybranej jednostki LUB dowolnej jednostki z jej rodziny MPTT (przodkowie +
sama + potomkowie). Odwzorowuje multiseek ``EQUAL_PLUS_SUB_FEMALE``:
``Q(autorzy__jednostka__in=value.get_family())``.
"""

import pytest
from djangoql.queryset import apply_search

pytestmark = pytest.mark.serial


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
    query = f'jednostka_z_podjednostkami__rel = "{jednostka.nazwa} [{jednostka.pk}]"'
    found = apply_search(Rekord.objects.all(), query, schema=BppQLSchema).distinct()

    assert found.count() == 1
    assert found.first().tytul_oryginalny == wydawnictwo_ciagle.tytul_oryginalny


@pytest.mark.django_db
def test_jednostka_z_podjednostkami_free_text_negation(
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    jednostka,
):
    """Operator != w fallbacku free-text (bez [pk]) wyklucza pasujące rekordy.

    Weryfikuje Fix 1: ``~q`` zamiast ``q`` gdy operator == "!="
    dla ścieżki bez identyfikatora numerycznego.
    """
    from denorm import denorms

    from bpp.djangoql_schema import BppQLSchema
    from bpp.models import Rekord

    # Autor przypisany bezpośrednio do ``jednostka`` (nazwa: "Jednostka Uczelni").
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()

    # Zapytanie pozytywne — powinno znaleźć tę publikację.
    pos_query = (
        f'jednostka_z_podjednostkami__rel = "{jednostka.nazwa}"'
    )
    pos = apply_search(Rekord.objects.all(), pos_query, schema=BppQLSchema).distinct()
    assert pos.count() == 1

    # Zapytanie negacyjne — ta sama wartość free-text, ale !=.
    # Bez Fix 1 zwróciłoby 1 (ignorując operator), powinno zwrócić 0.
    neg_query = (
        f'jednostka_z_podjednostkami__rel != "{jednostka.nazwa}"'
    )
    neg = apply_search(Rekord.objects.all(), neg_query, schema=BppQLSchema).distinct()
    assert neg.count() == 0
