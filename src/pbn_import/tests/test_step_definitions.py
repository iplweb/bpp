"""Tests for PBN import step definitions"""

import pytest

from pbn_import.utils.step_definitions import (
    ALL_STEP_DEFINITIONS,
    get_icon_for_step,
    get_step_definitions,
)


@pytest.mark.django_db
def test_get_step_definitions_default_config():
    """Test that all steps are enabled with empty/default config"""
    config = {}
    steps = get_step_definitions(config)

    # Should return all 9 steps when nothing is disabled
    # (data_integration was removed as redundant - publications are created
    # with pbn_uid_id already set, and statement integration is done in statement_import)
    assert len(steps) == 9

    # Verify step names in order
    expected_names = [
        "initial_setup",
        "institution_setup",
        "source_import",
        "publisher_import",
        "conference_import",
        "author_import",
        "publication_import",
        "statement_import",
        "fee_import",
    ]
    actual_names = [step["name"] for step in steps]
    assert actual_names == expected_names


@pytest.mark.django_db
def test_get_step_definitions_all_disabled():
    """Test that all steps are disabled when all flags are set"""
    config = {
        "disable_initial": True,
        "disable_institutions": True,
        "disable_zrodla": True,
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
    """Test that each disable flag works correctly"""
    # Test disabling initial_setup
    config = {"disable_initial": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "initial_setup" not in step_names
    assert len(steps) == 8

    # Test disabling institutions
    config = {"disable_institutions": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "institution_setup" not in step_names
    assert len(steps) == 8

    # Test disabling sources
    config = {"disable_zrodla": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "source_import" not in step_names
    assert len(steps) == 8

    # Test disabling publishers
    config = {"disable_wydawcy": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "publisher_import" not in step_names
    assert len(steps) == 8

    # Test disabling conferences
    config = {"disable_konferencje": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "conference_import" not in step_names
    assert len(steps) == 8

    # Test disabling authors
    config = {"disable_autorzy": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "author_import" not in step_names
    assert len(steps) == 8

    # Test disabling publications
    config = {"disable_publikacje": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "publication_import" not in step_names
    assert len(steps) == 8

    # Test disabling statements
    config = {"disable_oswiadczenia": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "statement_import" not in step_names
    assert len(steps) == 8

    # Test disabling fees
    config = {"disable_oplaty": True}
    steps = get_step_definitions(config)
    step_names = [step["name"] for step in steps]
    assert "fee_import" not in step_names
    assert len(steps) == 8


@pytest.mark.django_db
def test_get_step_definitions_preserves_order():
    """Test that step order matches ALL_STEP_DEFINITIONS"""
    config = {}
    steps = get_step_definitions(config)

    # Verify order matches ALL_STEP_DEFINITIONS
    for i, step in enumerate(steps):
        assert step["name"] == ALL_STEP_DEFINITIONS[i]["name"]
        assert step["display"] == ALL_STEP_DEFINITIONS[i]["display"]
        assert step["class"] == ALL_STEP_DEFINITIONS[i]["class"]
        assert step["required"] == ALL_STEP_DEFINITIONS[i]["required"]


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
    """Test that combination of disable flags works correctly"""
    config = {
        "disable_zrodla": True,
        "disable_wydawcy": True,
        "disable_konferencje": True,
    }
    steps = get_step_definitions(config)

    # Should have 6 steps (9 - 3 disabled)
    assert len(steps) == 6

    step_names = [step["name"] for step in steps]
    assert "source_import" not in step_names
    assert "publisher_import" not in step_names
    assert "conference_import" not in step_names

    # These should still be present
    assert "initial_setup" in step_names
    assert "institution_setup" in step_names
    assert "author_import" in step_names
    assert "publication_import" in step_names


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

    # Test unknown step (should return default)
    assert get_icon_for_step("unknown_step") == "fi-download"


@pytest.mark.django_db
def test_get_step_definitions_steps_with_empty_args():
    """Test that steps without dynamic args have empty args dict"""
    config = {}
    steps = get_step_definitions(config)

    # Steps without dynamic args
    steps_without_args = [
        "initial_setup",
        "source_import",
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
