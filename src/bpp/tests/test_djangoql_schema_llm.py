"""Testy ograniczonego schematu DjangoQL (allow-lista) + komendy eksportu dla LLM.

Patrz: docs/superpowers/specs/2026-07-10-djangoql-schema-dla-llm-design.md
"""

import json
from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command

from django_bpp.version import VERSION

Rekord = apps.get_model("bpp", "Rekord")


def test_search_allowlist_resolves_without_duplicates():
    from bpp.djangoql_schema import SEARCH_ALLOWLIST

    assert len(SEARCH_ALLOWLIST) == len(set(SEARCH_ALLOWLIST))
    assert Rekord in SEARCH_ALLOWLIST
    for model in SEARCH_ALLOWLIST:
        assert hasattr(model, "_meta")


@pytest.mark.django_db
def test_rekord_llm_schema_limited_to_allowlist():
    from bpp.djangoql_schema import SEARCH_ALLOWLIST, RekordLLMSchema

    schema = RekordLLMSchema(Rekord)
    allowed = {m._meta.label_lower for m in SEARCH_ALLOWLIST}
    assert set(schema.models).issubset(allowed)


@pytest.mark.django_db
def test_rekord_llm_schema_keeps_core_bibliographic_models():
    from bpp.djangoql_schema import RekordLLMSchema

    schema = RekordLLMSchema(Rekord)
    for label in (
        "bpp.rekord",
        "bpp.autor",
        "bpp.zrodlo",
        "bpp.charakter_formalny",
        "bpp.dyscyplina_naukowa",
    ):
        assert label in schema.models


@pytest.mark.django_db
def test_rekord_llm_schema_drops_sensitive_and_internal_models():
    from bpp.djangoql_schema import RekordLLMSchema

    schema = RekordLLMSchema(Rekord)
    for label in (
        "bpp.bppuser",
        "auth.user",
        "contenttypes.contenttype",
        "sites.site",
        "bpp.rekordview",
    ):
        assert label not in schema.models


@pytest.mark.django_db
def test_ograniczony_schema_start_model_is_rekord():
    from bpp.djangoql_schema import BppQLSchemaOgraniczony

    schema = BppQLSchemaOgraniczony(Rekord)
    assert schema.model_label(schema.current_model) == "bpp.rekord"


@pytest.mark.django_db
def test_ograniczony_schema_rejects_field_to_excluded_model():
    from djangoql.exceptions import DjangoQLSchemaError
    from djangoql.queryset import apply_search

    from bpp.djangoql_schema import BppQLSchemaOgraniczony

    # autorzy.autor.user -> bpp.bppuser jest poza allow-listą → odrzucone
    with pytest.raises(DjangoQLSchemaError):
        apply_search(
            Rekord.objects.all(),
            "autorzy.autor.user = None",
            schema=BppQLSchemaOgraniczony,
        )


@pytest.mark.django_db
def test_ograniczony_schema_accepts_bibliographic_and_pbn_query():
    from djangoql.queryset import apply_search

    from bpp.djangoql_schema import BppQLSchemaOgraniczony

    # zapytanie bibliograficzne + uratowana relacja PBN muszą się zbudować
    qs = apply_search(
        Rekord.objects.all(),
        'charakter_formalny.nazwa ~ "artyku" and rok >= 2000 and pbn_uid != None',
        schema=BppQLSchemaOgraniczony,
    )
    # wymuś złożenie SQL (bez ciężkiego fetchu)
    str(qs.query)


def test_view_and_multiseek_use_limited_schema():
    from bpp.djangoql_schema import BppQLSchemaOgraniczony
    from bpp.multiseek_registry.djangoql_export import _REKORD_SCHEMA
    from bpp.views.zapytanie import BppZapytanieSchema

    assert BppZapytanieSchema is BppQLSchemaOgraniczony
    assert isinstance(_REKORD_SCHEMA, BppQLSchemaOgraniczony)


@pytest.mark.django_db
def test_command_stdout_compact_has_version_header():
    out = StringIO()
    call_command("opisz_schemat_djangoql_dla_llm", "--drukuj", stdout=out)
    text = out.getvalue()
    assert text.startswith(f"# BPP {VERSION}")
    assert "start model: bpp.rekord" in text


@pytest.mark.django_db
def test_command_json_stdout_has_bpp_version_key():
    out = StringIO()
    call_command(
        "opisz_schemat_djangoql_dla_llm", "--drukuj", "--format", "json", stdout=out
    )
    data = json.loads(out.getvalue())
    assert data["bpp_version"] == VERSION
    assert data["start_model"] == "bpp.rekord"


@pytest.mark.django_db
def test_command_writes_output_file(tmp_path):
    target = tmp_path / "schema.compact.txt"
    call_command("opisz_schemat_djangoql_dla_llm", "--output", str(target))
    content = target.read_text()
    assert content.startswith(f"# BPP {VERSION}")
    assert "bpp.charakter_formalny:" in content


def test_llm_fk_options_targets_only_safe_dictionaries():
    """fk_options eksportu LLM osadza wartości WYŁĄCZNIE dla bezpiecznych
    słowników (standardowe tablice referencyjne BPP), nigdy dla modeli danych
    (publikacje, autorzy, jednostki, encje PBN). Test niezależny od bazy."""
    from bpp.djangoql_schema import (  # noqa: PLC2701
        _EMBED_ALL_VALUES,
        _SAFE_VALUE_TARGET_LABELS,
        RekordLLMSchema,
    )

    safe = {
        apps.get_model(label)._meta.label_lower for label in _SAFE_VALUE_TARGET_LABELS
    }
    opts = RekordLLMSchema.fk_options

    # bezpieczny słownik osadza KOMPLET wartości (charakter_formalny to
    # standardowa tablica); marker to per-relacyjny limit int (djangoql
    # >= 0.31.1), nie True — True obcinałoby do 20.
    assert opts.get(Rekord, {}).get("charakter_formalny") == _EMBED_ALL_VALUES
    # KAŻDY wpis fk_options celuje w bezpieczny słownik
    for owner, fields in opts.items():
        for field_name in fields:
            target = owner._meta.get_field(field_name).related_model
            assert target._meta.label_lower in safe, f"{owner}.{field_name} → {target}"
    # relacja do modelu danych (wydawca = encja, nie słownik) NIE osadza wartości
    assert "wydawca" not in opts.get(Rekord, {})


def test_uczelnia_exposes_only_nazwa_and_skrot():
    """Uczelnia trzyma hasła (dspace/pbn/clarivate/orcid) i dziesiątki ustawień —
    w schemacie wyszukiwania udostępniamy tylko identyfikujące nazwa/skrot."""
    from bpp.djangoql_schema import BppQLSchemaOgraniczony, RekordLLMSchema

    for schema_cls in (RekordLLMSchema, BppQLSchemaOgraniczony):
        fields = set(schema_cls(Rekord).models["bpp.uczelnia"])
        assert fields == {"nazwa", "skrot"}, f"{schema_cls.__name__}: {fields}"


def test_uczelnia_secrets_never_in_any_schema():
    from bpp.djangoql_schema import BppQLSchemaOgraniczony, RekordLLMSchema

    for schema_cls in (RekordLLMSchema, BppQLSchemaOgraniczony):
        fields = set(schema_cls(Rekord).models["bpp.uczelnia"])
        for secret in (
            "dspace_api_password",
            "pbn_app_token",
            "orcid_client_secret",
            "clarivate_password",
        ):
            assert secret not in fields


def test_legacy_named_fields_dropped():
    """Pola z 'legacy' w nazwie (legacy_data itp.) nie trafiają do schematu."""
    from bpp.djangoql_schema import RekordLLMSchema

    fields = set(RekordLLMSchema(Rekord).models["bpp.wydawnictwo_ciagle"])
    assert "legacy_data" not in fields


def test_historical_marked_fields_dropped_but_current_kept():
    """Pola oznaczone '[Pole o znaczeniu historycznym]' (pbn_id) wypadają;
    aktualny odpowiednik (pbn_uid) zostaje."""
    from bpp.djangoql_schema import BppQLSchemaOgraniczony, RekordLLMSchema

    for schema_cls in (RekordLLMSchema, BppQLSchemaOgraniczony):
        fields = set(schema_cls(Rekord).models["bpp.wydawnictwo_ciagle"])
        assert "pbn_id" not in fields
        assert "pbn_uid" in fields


def test_llm_schema_declares_org_names_as_no_value_targets():
    """RekordLLMSchema deklaruje twardą listę celów (jednostka/wydział/uczelnia),
    których nazwy nie mają prawa trafić do artefaktu niezależnie od max-fk.
    Test niezależny od bazy i od wersji djangoql-iplweb."""
    from bpp.djangoql_schema import RekordLLMSchema

    assert set(RekordLLMSchema.no_value_targets) >= {
        "bpp.Jednostka",
        "bpp.Wydzial",
        "bpp.Uczelnia",
    }


@pytest.mark.django_db
def test_org_unit_names_never_emitted_even_at_max_fk():
    """Twarda gwarancja (no_value_targets): nawet przy --max-fk-options 50 i
    małej liczbie wierszy, nazwy jednostek/uczelni NIE trafiają do opisu.
    Wymaga djangoql-iplweb >= 0.30.3."""
    from djangoql.llm import describe_schema_for_llm
    from model_bakery import baker

    from bpp.djangoql_schema import RekordLLMSchema
    from bpp.models import Jednostka, Uczelnia

    ucz = baker.make(Uczelnia, nazwa="TAJNA-UCZELNIA-XYZ")
    baker.make(Jednostka, nazwa="TAJNA-JEDNOSTKA-XYZ", uczelnia=ucz)

    out = describe_schema_for_llm(
        RekordLLMSchema(Rekord), format="compact", max_fk_options=50
    )
    assert "TAJNA-JEDNOSTKA-XYZ" not in out
    assert "TAJNA-UCZELNIA-XYZ" not in out


@pytest.mark.django_db
def test_committed_artifact_has_no_institution_data_leak(tmp_path):
    """Domyślna generacja (max-fk-options=0) NIE osadza wartości wierszy tabel
    danych (tytuły publikacji, abstrakty) — żeby do repo open-source nie
    trafiały dane konkretnej instytucji."""
    import re

    target = tmp_path / "schema.compact.txt"
    call_command("opisz_schemat_djangoql_dla_llm", "--output", str(target))
    content = target.read_text()

    assert content.startswith(f"# BPP {VERSION}")
    assert "bpp.charakter_formalny:" in content  # słownik jako sekcja modelu
    # relacja do dużej tabeli danych NIE osadza tytułów publikacji ani abstraktów
    assert not re.search(r'-> bpp\.rekord\??\s+match tytul in \("[^"]', content), (
        "wartości tabeli danych (tytuły) wyciekły do artefaktu"
    )
    assert "match streszczenie in" not in content, "abstrakt wyciekł do artefaktu"


@pytest.mark.django_db
def test_llm_schema_ukrywa_pola_pii_dla_api():
    """RekordLLMSchema (API /zapytanie/ + eksport LLM) NIE wystawia pól
    wolnotekstowych/PII, które dałyby się oracle-ować przez filtr, mimo że nie
    są zwracane w odpowiedzi: email/adnotacje/opis autora, email jednostki,
    adnotacje rekordu i podtypów publikacji. Świadomie zachowane (decyzja):
    poprzednie_nazwiska, system_kadrowy_id, pbn_uid (trawersacja do PBN)."""
    from bpp.djangoql_schema import RekordLLMSchema

    schema = RekordLLMSchema(Rekord)
    autor = set(schema.models["bpp.autor"])
    assert "email" not in autor
    assert "adnotacje" not in autor
    assert "opis" not in autor
    # zachowane wg decyzji użytkownika
    assert "poprzednie_nazwiska" in autor
    assert "system_kadrowy_id" in autor
    assert "pbn_uid" in autor

    assert "email" not in set(schema.models["bpp.jednostka"])
    assert "adnotacje" not in set(schema.models["bpp.rekord"])
    assert "adnotacje" not in set(schema.models["bpp.wydawnictwo_ciagle"])


@pytest.mark.django_db
def test_web_editor_schema_pii_nienaruszony():
    """Kontrakt web-edytora /zapytanie/ (BppQLSchemaOgraniczony) celowo NIE jest
    okrojony — redaktor w przeglądarce dalej filtruje po email/adnotacje
    (EXAMPLES zawiera 'email = ...'). Blocklist dotyczy tylko schematu
    agent-facing."""
    from bpp.djangoql_schema import BppQLSchemaOgraniczony

    schema = BppQLSchemaOgraniczony(Rekord)
    autor = set(schema.models["bpp.autor"])
    assert "email" in autor
    assert "adnotacje" in autor
    assert "adnotacje" in set(schema.models["bpp.rekord"])
