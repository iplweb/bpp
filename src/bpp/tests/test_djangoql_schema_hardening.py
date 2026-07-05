"""Testy uszczelnienia współdzielonej ``BppQLSchema`` (DjangoQL).

Patrz docstring modułu ``bpp.djangoql_schema`` oraz brief zadania:
wyciek `autorzy.autor.user.password_change_required` (traversal do
`password_policies` przez `BppUser`) musi przestać być wyrażalny, a graf
modeli (BFS z `Rekord`) musi się odchudzić o aplikacje robocze/wrażliwe.
"""

import pytest
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Rekord


@pytest.mark.django_db
def test_password_change_required_traversal_closed():
    """Wyciek zamknięty: nie da się dojść do password_policies przez BppUser."""
    with pytest.raises(DjangoQLError):
        apply_search(
            Rekord.objects.all(),
            "autorzy.autor.user.password_change_required != None",
            schema=BppQLSchema,
        )


@pytest.mark.django_db
def test_bppuser_fields_truncated_to_allowlist():
    """BppUser: tylko username/nazwisko/imiona — bez hasła/uprawnień/emaila."""
    schema = BppQLSchema(Rekord)
    label = "bpp.bppuser"
    if label not in schema.models:
        pytest.skip("bpp.bppuser nieosiągalny w grafie — allowlista bez znaczenia")
    fields = set(schema.models[label])
    assert fields <= {"username", "nazwisko", "imiona"}
    for sensitive in ("password", "is_superuser", "email", "pbn_token"):
        assert sensitive not in fields


@pytest.mark.django_db
def test_excluded_model_absent_from_graph():
    """Model z twardej listy wykluczeń (easyaudit) nie występuje w grafie."""
    schema = BppQLSchema(Rekord)
    assert "easyaudit.crudevent" not in schema.models


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "rok = 2024",
        'autorzy.autor.nazwisko ~ "Kowalski"',
        'charakter_formalny.skrot = "AC"',
        'typ_kbn.skrot = "PO"',
        'zrodlo.nazwa ~ "x"',
        "pbn_uid != None",
    ],
)
def test_core_queries_still_parse(query):
    """Rdzeń funkcjonalny (edytor/admin) musi dalej działać po uszczelnieniu."""
    apply_search(Rekord.objects.all(), query, schema=BppQLSchema)


@pytest.mark.django_db
def test_dictionary_models_remain_in_graph():
    """Słowniki (charakter_formalny, typ_kbn) zostają w grafie."""
    schema = BppQLSchema(Rekord)
    assert "bpp.charakter_formalny" in schema.models
    assert "bpp.typ_kbn" in schema.models


@pytest.mark.django_db
def test_graph_significantly_smaller():
    """Graf modeli mocno się kurczy po wykluczeniu aplikacji roboczych.

    Przed uszczelnieniem: 216 modeli (BFS z Rekord). Po: 87 (bpp + pbn_api +
    pbn_export_queue + taggit — żadna z wykluczonych app_labels). Próg < 100
    zamiast przykładowego < 60 z briefu, bo `pbn_api` (celowo NIE wykluczone,
    niesie `pbn_uid`) oraz jego własne relacje (Publication, Institution,
    Scientist, Journal, …) dociągają część grafu z powrotem — patrz raport."""
    schema = BppQLSchema(Rekord)
    assert len(schema.models) < 100
