"""Tests for PBN import step definitions"""

import pytest

from pbn_import.utils.step_definitions import (
    ALL_STEP_DEFINITIONS,
    get_all_disable_keys,
    get_form_steps,
    get_icon_for_step,
    get_step_definitions,
)


@pytest.mark.django_db
def test_get_step_definitions_default_config():
    steps = get_step_definitions({})
    assert len(steps) == 16
    keys = [s["result_key"] for s in steps]
    assert keys == [
        "initial_setup",
        "institution_setup",
        "source_import:download",
        "source_import:process",
        "source_scoring_import",
        "publisher_import:download",
        "publisher_import:process",
        "conference_import:download",
        "conference_import:process",
        "author_import:download",
        "author_import:process",
        "publication_import:download",
        "publication_import:process",
        "statement_import:download",
        "statement_import:process",
        "fee_import",
    ]


@pytest.mark.django_db
def test_get_step_definitions_all_disabled():
    """Test that all steps are disabled when all flags are set"""
    config = {
        "disable_initial": True,
        "disable_institutions": True,
        "disable_zrodla": True,
        "disable_punktacja_zrodel": True,
        "disable_wydawcy": True,
        "disable_konferencje": True,
        "disable_autorzy": True,
        "disable_publikacje": True,
        "disable_oswiadczenia": True,
        "disable_oplaty": True,
    }
    steps = get_step_definitions(config)

    # Should return no steps when all are disabled
    assert len(steps) == 0


@pytest.mark.django_db
def test_get_step_definitions_individual_disable_flags():
    keys = [s["result_key"] for s in get_step_definitions({"disable_zrodla": True})]
    assert "source_import:download" not in keys
    assert "source_import:process" not in keys
    assert len(keys) == 14
    keys = [s["result_key"] for s in get_step_definitions({"disable_oplaty": True})]
    assert "fee_import" not in keys
    assert len(keys) == 15
    keys = [
        s["result_key"]
        for s in get_step_definitions({"disable_punktacja_zrodel": True})
    ]
    assert "source_scoring_import" not in keys
    assert len(keys) == 15


@pytest.mark.django_db
def test_get_step_definitions_preserves_order():
    keys = [s["result_key"] for s in get_step_definitions({})]
    assert keys.index("source_import:download") < keys.index("source_import:process")
    assert keys.index("source_import:process") < keys.index("publisher_import:download")
    entity_order = [
        s["name"] for s in get_step_definitions({}) if s["phase"] != "process"
    ]
    expected = [d["name"] for d in ALL_STEP_DEFINITIONS]
    seen = []
    for n in entity_order:
        if n not in seen:
            seen.append(n)
    assert seen == expected


@pytest.mark.django_db
def test_get_step_definitions_dynamic_args_institution():
    """Test that institution_setup gets correct dynamic args from config"""
    config = {
        "wydzial_domyslny": "Wydział Testowy",
        "wydzial_domyslny_skrot": "WT",
    }
    steps = get_step_definitions(config)

    # Find institution_setup step
    institution_step = next(
        (step for step in steps if step["name"] == "institution_setup"), None
    )
    assert institution_step is not None

    # Verify dynamic args
    assert institution_step["args"]["wydzial_domyslny"] == "Wydział Testowy"
    assert institution_step["args"]["wydzial_domyslny_skrot"] == "WT"


@pytest.mark.django_db
def test_get_step_definitions_dynamic_args_institution_defaults():
    """Test that institution_setup uses default values when not in config"""
    config = {}
    steps = get_step_definitions(config)

    # Find institution_setup step
    institution_step = next(
        (step for step in steps if step["name"] == "institution_setup"), None
    )
    assert institution_step is not None

    # Verify default args
    assert institution_step["args"]["wydzial_domyslny"] == "Wydział Domyślny"
    assert institution_step["args"]["wydzial_domyslny_skrot"] is None


@pytest.mark.django_db
def test_get_step_definitions_dynamic_args_publication():
    """Test that publication_import gets correct dynamic args from config"""
    config = {"delete_existing": True}
    steps = get_step_definitions(config)

    # Find publication_import step
    publication_step = next(
        (step for step in steps if step["name"] == "publication_import"), None
    )
    assert publication_step is not None

    # Verify dynamic args
    assert publication_step["args"]["delete_existing"] is True


@pytest.mark.django_db
def test_get_step_definitions_dynamic_args_publication_default():
    """Test that publication_import uses default delete_existing=False"""
    config = {}
    steps = get_step_definitions(config)

    # Find publication_import step
    publication_step = next(
        (step for step in steps if step["name"] == "publication_import"), None
    )
    assert publication_step is not None

    # Verify default args
    assert publication_step["args"]["delete_existing"] is False


@pytest.mark.django_db
def test_get_step_definitions_step_structure():
    """Test that each step has required keys and correct structure"""
    config = {}
    steps = get_step_definitions(config)

    required_keys = ["name", "display", "class", "required", "args"]

    for step in steps:
        # Verify all required keys are present
        for key in required_keys:
            assert key in step, f"Step {step.get('name')} missing key: {key}"

        # Verify types
        assert isinstance(step["name"], str)
        assert isinstance(step["display"], str)
        assert callable(step["class"])
        assert isinstance(step["required"], bool)
        assert isinstance(step["args"], dict)


@pytest.mark.django_db
def test_get_step_definitions_combination_of_flags():
    config = {
        "disable_zrodla": True,
        "disable_wydawcy": True,
        "disable_konferencje": True,
    }
    steps = get_step_definitions(config)
    names = {s["name"] for s in steps}
    assert len(steps) == 10
    assert "source_import" not in names
    assert "publisher_import" not in names
    assert "conference_import" not in names
    assert "initial_setup" in names
    assert "institution_setup" in names
    assert "source_scoring_import" in names
    assert "author_import" in names
    assert "publication_import" in names


@pytest.mark.django_db
def test_get_icon_for_step():
    """Test that get_icon_for_step returns correct icons"""
    # Test known steps
    assert get_icon_for_step("initial_setup") == "fi-wrench"
    assert get_icon_for_step("institution_setup") == "fi-home"
    assert get_icon_for_step("source_import") == "fi-book"
    assert get_icon_for_step("publisher_import") == "fi-page-multiple"
    assert get_icon_for_step("conference_import") == "fi-calendar"
    assert get_icon_for_step("author_import") == "fi-torsos-all"
    assert get_icon_for_step("publication_import") == "fi-page-copy"
    assert get_icon_for_step("statement_import") == "fi-clipboard-pencil"
    assert get_icon_for_step("fee_import") == "fi-dollar"
    assert get_icon_for_step("source_scoring_import") == "fi-graph-bar"

    # Test unknown step (should return default)
    assert get_icon_for_step("unknown_step") == "fi-download"


@pytest.mark.django_db
def test_get_step_definitions_steps_with_empty_args():
    """Test that steps without dynamic args have empty args dict"""
    config = {}
    steps = get_step_definitions(config)

    # Steps without dynamic args — with phase model, steps appear per-phase;
    # use name match (first occurrence covers both download & process phases)
    steps_without_args = [
        "initial_setup",
        "source_import",
        "source_scoring_import",
        "publisher_import",
        "conference_import",
        "author_import",
        "statement_import",
        "fee_import",
    ]

    for step_name in steps_without_args:
        step = next((s for s in steps if s["name"] == step_name), None)
        assert step is not None
        assert step["args"] == {}


# --- nowe testy (Task 9: model faz) ---


def test_split_step_emits_two_phases_in_order():
    defs = get_step_definitions({})
    keys = [d["result_key"] for d in defs]
    assert keys.index("source_import:download") < keys.index("source_import:process")
    assert "conference_import:download" in keys
    assert "conference_import:process" in keys


def test_each_phase_carries_method():
    defs = get_step_definitions({})
    by_key = {d["result_key"]: d for d in defs}
    assert by_key["source_import:download"]["method"] == "download"
    assert by_key["source_import:process"]["method"] == "process"
    assert by_key["fee_import"]["method"] == "run"


def test_granular_disable_skips_one_phase_only():
    defs = get_step_definitions({"disable_zrodla_download": True})
    keys = [d["result_key"] for d in defs]
    assert "source_import:download" not in keys
    assert "source_import:process" in keys


def test_legacy_key_disables_both_phases():
    defs = get_step_definitions({"disable_zrodla": True})
    keys = [d["result_key"] for d in defs]
    assert "source_import:download" not in keys
    assert "source_import:process" not in keys


def test_granular_overrides_legacy():
    defs = get_step_definitions(
        {"disable_zrodla": True, "disable_zrodla_process": False}
    )
    keys = [d["result_key"] for d in defs]
    assert "source_import:process" in keys
    assert "source_import:download" not in keys


def test_get_all_disable_keys_is_granular():
    mapping = get_all_disable_keys()
    assert mapping["zrodla_download"] == "disable_zrodla_download"
    assert mapping["zrodla_process"] == "disable_zrodla_process"
    assert mapping["oplaty"] == "disable_oplaty"


def test_get_form_steps_returns_two_column_rows():
    rows = get_form_steps()
    by_name = {r["name"]: r for r in rows}
    zrodla = by_name["source_import"]
    assert zrodla["download"]["form_field"] == "zrodla_download"
    assert zrodla["process"]["form_field"] == "zrodla_process"
    punktacja = by_name["source_scoring_import"]
    assert punktacja["download"] is None
    assert punktacja["process"] is not None
    oplaty = by_name["fee_import"]
    assert oplaty["single"] is not None
