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
def test_uczelnia_fields_truncated_to_allowlist():
    """Uczelnia: tylko id/nazwa/skrot/pbn_uid (± picker pbn_uid__rel) — bez
    pól konfiguracyjnych (integracje, hasła zewnętrznych API, ustawienia UI)."""
    schema = BppQLSchema(Rekord)
    label = "bpp.uczelnia"
    if label not in schema.models:
        pytest.skip("bpp.uczelnia nieosiągalny w grafie — allowlista bez znaczenia")
    fields = set(schema.models[label])
    allowed = {"id", "nazwa", "skrot", "pbn_uid"}
    assert fields <= allowed | {f"{name}__rel" for name in allowed}
    for config_field in (
        "pbn_integracja",
        "wyszukiwanie_rekordy_na_strone_anonim",
        "pbn_api_user",
        "clarivate_password",
        "dspace_api_password",
        "orcid_client_secret",
    ):
        assert config_field not in fields


@pytest.mark.django_db
def test_uczelnia_picker_does_not_bypass_filter():
    """Pickery ``<fk>__rel`` nie omijają include_fields: żaden picker uczelni
    nie wskazuje na pole spoza allowlisty (np. relacji config-owej)."""
    schema = BppQLSchema(Rekord)
    label = "bpp.uczelnia"
    if label not in schema.models:
        pytest.skip("bpp.uczelnia nieosiągalny w grafie — test bez znaczenia")
    fields = set(schema.models[label])
    allowed_base = {"id", "nazwa", "skrot", "pbn_uid"}
    for name in fields:
        if name.endswith("__rel"):
            base = name[: -len("__rel")]
            assert base in allowed_base, (
                f"picker {name!r} wskazuje na pole spoza include_fields "
                f"({base!r} nie jest w {allowed_base!r}) — filtr obejdziony"
            )


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
