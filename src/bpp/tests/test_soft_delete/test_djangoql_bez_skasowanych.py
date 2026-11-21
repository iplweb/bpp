"""DjangoQL domyślnie NIE pokazuje kosza, ale da się o niego jawnie poprosić.

* zapytanie przechodzące przez relację do modelu soft-delete (publikacja,
  autor) albo do dziecka publikacji bez własnego kosza (``*_Autor`` —
  wtedy predykat idzie na ``rekord``) dostaje domyślny predykat
  ``deleted_at = None`` na TYM SAMYM JOIN-ie;
* wzmianka o ``deleted_at`` na danej ścieżce zdejmuje predykat
  (``!= None`` = tylko kosz).

Szczegóły: ``bpp/djangoql_soft_delete.py``.
"""

import pytest
from djangoql.queryset import apply_search

from bpp.djangoql_schema import BppQLSchema, BppQLSchemaOgraniczony, RekordLLMSchema
from bpp.models import Autor


def _pk_set(qs):
    return set(qs.values_list("pk", flat=True))


def _szukaj_autorow(zapytanie, schema=BppQLSchema):
    return _pk_set(apply_search(Autor.objects.all(), zapytanie, schema=schema))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "schema", [BppQLSchema, BppQLSchemaOgraniczony, RekordLLMSchema]
)
def test_autorstwo_publikacji_z_kosza_niewidoczne(wydawnictwo_ciagle_z_autorem, schema):
    """Ścieżka nie przechodzi przez ``rekord`` — predykat i tak ląduje na
    rodzicu (``wydawnictwo_ciagle_autor__rekord__deleted_at``)."""
    wc = wydawnictwo_ciagle_z_autorem
    autorstwo = wc.autorzy_set.first()
    zapytanie = f"wydawnictwo_ciagle_autor.kolejnosc = {autorstwo.kolejnosc}"

    assert autorstwo.autor_id in _szukaj_autorow(zapytanie, schema)

    wc.delete()

    assert autorstwo.autor_id not in _szukaj_autorow(zapytanie, schema)


@pytest.mark.django_db
def test_jawne_pytanie_o_kosz_rodzica(wydawnictwo_ciagle_z_autorem):
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    wc.delete()

    zapytanie = (
        f"wydawnictwo_ciagle_autor.rekord.id = {wc.pk} "
        "and wydawnictwo_ciagle_autor.rekord.deleted_at != None"
    )
    assert autor_id in _szukaj_autorow(zapytanie)
    assert autor_id not in _szukaj_autorow(
        f"wydawnictwo_ciagle_autor.rekord.id = {wc.pk}"
    )


@pytest.mark.django_db
def test_agregat_nie_liczy_autorstw_z_kosza(wydawnictwo_ciagle_z_autorem):
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    zapytanie = f"id = {autor_id} and wydawnictwo_ciagle_autor__count > 0"

    assert autor_id in _szukaj_autorow(zapytanie)
    wc.delete()
    assert autor_id not in _szukaj_autorow(zapytanie)


@pytest.mark.django_db
def test_dlugowieczna_instancja_schematu_nie_pamieta_prosby_o_kosz(
    wydawnictwo_ciagle_z_autorem,
):
    """Instancja schematu bywa singletonem — prośba o kosz z jednego
    zapytania nie może przeciekać na następne."""
    from djangoql.parser import DjangoQLParser
    from djangoql.queryset import build_filter

    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    wc.delete()

    schemat = BppQLSchema(Autor)

    def _uruchom(zapytanie):
        ast = DjangoQLParser().parse(zapytanie)
        schemat.validate(ast)
        return _pk_set(Autor.objects.filter(build_filter(ast, schemat)))

    baza = f"wydawnictwo_ciagle_autor.rekord.id = {wc.pk}"
    assert autor_id in _uruchom(
        baza + " and wydawnictwo_ciagle_autor.rekord.deleted_at != None"
    )
    assert autor_id not in _uruchom(baza)
