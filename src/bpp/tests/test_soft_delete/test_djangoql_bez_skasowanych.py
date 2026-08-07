"""DjangoQL domyślnie NIE pokazuje kosza (soft-delete), ale da się go
jawnie poprosić o pokazanie.

Kontrakt (zmiana decyzji z fazy „wyciek ORM", commit ``e80d1656e``, gdzie
DjangoQL świadomie zostawiono surowy):

* zapytanie, które przechodzi przez relację do modelu soft-delete i NIE
  wspomina ``deleted_at`` na tej relacji, dostaje domyślny predykat
  ``<relacja>.deleted_at = None`` **na tym samym JOIN-ie**;
* zapytanie, które wspomina ``deleted_at`` na danej relacji, NIE dostaje nic
  — użytkownik świadomie steruje koszem (``!= None`` = tylko kosz).

Testy semantyczne (nie substringowe) — patrz ``bpp/djangoql_soft_delete.py``.
"""

import pytest
from djangoql.queryset import apply_search

from bpp.djangoql_schema import BppQLSchema, BppQLSchemaOgraniczony, RekordLLMSchema
from bpp.models import Autor, Wydawnictwo_Ciagle


def _pk_set(qs):
    return set(qs.values_list("pk", flat=True))


def _szukaj_wc(zapytanie, schema=BppQLSchema):
    return _pk_set(
        apply_search(Wydawnictwo_Ciagle.objects.all(), zapytanie, schema=schema)
    )


@pytest.mark.django_db
def test_djangoql_domyslnie_odsiewa_skasowane_autorstwo(wydawnictwo_ciagle_z_autorem):
    """Zapytanie BEZ wzmianki o ``deleted_at`` nie widzi skasowanego
    autorstwa — wcześniej JOIN po ``autorzy_set`` pokazywał husk."""
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    zapytanie = f"autorzy_set.autor.id = {autor_id}"

    assert wc.pk in _szukaj_wc(zapytanie)

    wc.autorzy_set.first().delete()

    assert wc.pk not in _szukaj_wc(zapytanie)


@pytest.mark.django_db
def test_djangoql_jawny_warunek_pokazuje_kosz(wydawnictwo_ciagle_z_dwoma_autorami):
    """Jawne ``deleted_at != None`` na tej samej relacji ZDEJMUJE domyślny
    predykat — narzędzie audytowe dalej działa, tylko trzeba o kosz poprosić.

    Publikacja ma DWA autorstwa (jedno zostanie skasowane, drugie żyje) —
    wyrocznia na to, że ``!= None`` jest skorelowane z tym samym JOIN-em.
    Gdyby zostało zanegowanym ``~Q(deleted_at = None)``, Django zrobiłby
    z tego „publikacja nie ma ŻADNEGO żywego autorstwa" i żywy współautor
    zabrałby wynik.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    autorstwo = wc.autorzy_set.order_by("kolejnosc").first()
    autor_id = autorstwo.autor_id
    zapytanie = f"autorzy_set.autor.id = {autor_id} and autorzy_set.deleted_at != None"

    assert wc.pk not in _szukaj_wc(zapytanie)

    autorstwo.delete()

    assert wc.pk in _szukaj_wc(zapytanie)


@pytest.mark.django_db
def test_djangoql_jawne_deleted_at_none_nadal_dziala(wydawnictwo_ciagle_z_autorem):
    """Jawne ``deleted_at = None`` (zapytanie deduplikatora) daje ten sam
    wynik co domyślne odsiewanie — dublowanie predykatu nic nie psuje."""
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    zapytanie = f"autorzy_set.autor.id = {autor_id} and autorzy_set.deleted_at = None"

    assert wc.pk in _szukaj_wc(zapytanie)

    wc.autorzy_set.first().delete()

    assert wc.pk not in _szukaj_wc(zapytanie)


@pytest.mark.django_db
def test_djangoql_predykat_jest_skorelowany_z_tym_samym_joinem(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """Predykat MUSI wisieć na tym samym JOIN-ie co warunek użytkownika.

    Wyrocznia: publikacja z DWOMA autorstwami, z których jedno skasowano.
    Nieskorelowany predykat (osobny ``.filter()``) dałby „istnieje jakieś
    żywe autorstwo" i przepuściłby zapytanie o autora skasowanego.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    pierwsze = wc.autorzy_set.order_by("kolejnosc").first()
    drugie = wc.autorzy_set.order_by("kolejnosc").last()
    assert pierwsze.pk != drugie.pk

    skasowany_autor_id = pierwsze.autor_id
    zywy_autor_id = drugie.autor_id
    pierwsze.delete()

    # Żywe autorstwo (drugi autor) NIE może „uratować" zapytania o autora,
    # którego autorstwo skasowano.
    assert wc.pk not in _szukaj_wc(f"autorzy_set.autor.id = {skasowany_autor_id}")
    assert wc.pk in _szukaj_wc(f"autorzy_set.autor.id = {zywy_autor_id}")


@pytest.mark.django_db
def test_djangoql_negacja_na_relacji_jest_zachowawcza(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """ŚLEPA PLAMA (przypięta świadomie): operator negujący na ścieżce
    relacyjnej NIE dostaje predykatu — patrz „Znane ślepe plamy" w
    ``bpp/djangoql_soft_delete.py``.

    Django dekoreluje negację na relacji wielowartościowej, więc predykat
    wciągnięty pod ``~`` zmieniałby znaczenie zapytania zamiast zawężać
    wiersz. Skutek: skasowane autorstwo nadal WYKLUCZA publikację z wyniku
    ``!=``. To tryb ZACHOWAWCZY — kosz się nie ujawnia, wynik bywa węższy.

    Test istnieje po to, żeby ograniczenie było widoczne i żeby jego
    przyszła naprawa (``exclude(rel__in=Subquery)``) zapaliła czerwone
    światło tutaj, a nie u użytkownika.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    pierwsze = wc.autorzy_set.order_by("kolejnosc").first()
    skasowany_autor_id = pierwsze.autor_id

    assert wc.pk not in _szukaj_wc(f"autorzy_set.autor.id != {skasowany_autor_id}")

    pierwsze.delete()

    assert wc.pk not in _szukaj_wc(f"autorzy_set.autor.id != {skasowany_autor_id}")


@pytest.mark.django_db
def test_djangoql_agregat_count_nie_liczy_kosza(wydawnictwo_ciagle_z_dwoma_autorami):
    """``autorzy_set__count`` filtruje skorelowanym PODZAPYTANIEM, nie
    JOIN-em — źródłem jest ``related_model._base_manager`` (goły ``Manager``,
    NIE nasz ``BppSoftDeleteManager``). Bez podmiany źródła agregat
    zawyżałby licznik o kosz."""
    wc = wydawnictwo_ciagle_z_dwoma_autorami

    assert wc.pk in _szukaj_wc("autorzy_set__count = 2")

    wc.autorzy_set.order_by("kolejnosc").first().delete()

    assert wc.pk not in _szukaj_wc("autorzy_set__count = 2")
    assert wc.pk in _szukaj_wc("autorzy_set__count = 1")

    # …a jawna wzmianka o koszu na tej samej relacji zdejmuje odsiewanie
    # również z agregatu (licznik znów obejmuje skasowane autorstwo).
    assert wc.pk in _szukaj_wc(
        "autorzy_set__count = 2 and autorzy_set.deleted_at != None"
    )


@pytest.mark.django_db
def test_schemat_ograniczony_i_llm_maja_ten_sam_kontrakt(
    wydawnictwo_ciagle_z_autorem,
):
    """Wszystkie trzy schematy BPP (admin, web-edytor, API/LLM) odsiewają
    kosz tak samo — inaczej ten sam string zapytania dawałby różne wyniki
    w zależności od punktu wejścia."""
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    wc.autorzy_set.first().delete()

    for schema in (BppQLSchema, BppQLSchemaOgraniczony, RekordLLMSchema):
        assert wc.pk not in _szukaj_wc(
            f"autorzy_set.autor.id = {autor_id}", schema=schema
        ), schema.__name__


@pytest.mark.django_db
def test_api_zapytanie_autor_nie_widzi_skasowanego_autorstwa(
    wydawnictwo_ciagle_z_autorem,
):
    """Ścieżka ``/api/v1/zapytanie/autor/`` (``RekordLLMSchema`` na korzeniu
    ``Autor``) — JOIN po ``wydawnictwo_ciagle_autor``."""
    wc = wydawnictwo_ciagle_z_autorem
    autorstwo = wc.autorzy_set.first()
    zapytanie = f"wydawnictwo_ciagle_autor.rekord.id = {wc.pk}"

    def _autorzy(q):
        return _pk_set(apply_search(Autor.objects.all(), q, schema=RekordLLMSchema))

    assert autorstwo.autor_id in _autorzy(zapytanie)

    autorstwo.delete()

    assert autorstwo.autor_id not in _autorzy(zapytanie)
    assert autorstwo.autor_id in _autorzy(
        zapytanie + " and wydawnictwo_ciagle_autor.deleted_at != None"
    )
