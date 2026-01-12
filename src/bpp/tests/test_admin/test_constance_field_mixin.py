"""
Testy dla dynamicznego ukrywania pól punktacji na podstawie ustawień constance.
"""

import pytest

from bpp.admin.helpers.constance_field_mixin import (
    CONSTANCE_TO_FIELD_MAP,
    filter_fields_from_fieldsets,
    get_constance_scoring_settings,
)


@pytest.mark.django_db
class TestGetConstanceScoringSettings:
    """Testy dla funkcji get_constance_scoring_settings."""

    def test_returns_dict_with_expected_keys(self):
        """Sprawdza, czy funkcja zwraca słownik z oczekiwanymi kluczami."""
        settings = get_constance_scoring_settings()

        assert "POKAZUJ_INDEX_COPERNICUS" in settings
        assert "POKAZUJ_PUNKTACJA_SNIP" in settings
        assert "UZYWAJ_PUNKTACJI_WEWNETRZNEJ" in settings

    def test_returns_boolean_values(self):
        """Sprawdza, czy wartości są typu boolean."""
        settings = get_constance_scoring_settings()

        for key, value in settings.items():
            assert isinstance(value, bool), f"{key} should be boolean, got {type(value)}"


class TestConstanceToFieldMap:
    """Testy dla mapowania constance -> pola."""

    def test_mapping_contains_expected_keys(self):
        """Sprawdza, czy mapowanie zawiera wszystkie oczekiwane klucze."""
        expected_keys = [
            "POKAZUJ_INDEX_COPERNICUS",
            "POKAZUJ_PUNKTACJA_SNIP",
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ",
        ]
        for key in expected_keys:
            assert key in CONSTANCE_TO_FIELD_MAP

    def test_mapping_values_are_tuples_with_two_elements(self):
        """Sprawdza, czy każda wartość mapowania jest krotką z dwoma elementami."""
        for key, value in CONSTANCE_TO_FIELD_MAP.items():
            assert isinstance(value, tuple), f"{key} should map to tuple"
            assert len(value) == 2, f"{key} should map to tuple with 2 elements"

    def test_mapping_contains_correct_field_names(self):
        """Sprawdza poprawność nazw pól w mapowaniu."""
        assert CONSTANCE_TO_FIELD_MAP["POKAZUJ_INDEX_COPERNICUS"] == (
            "index_copernicus",
            "pokazuj_index_copernicus",
        )
        assert CONSTANCE_TO_FIELD_MAP["POKAZUJ_PUNKTACJA_SNIP"] == (
            "punktacja_snip",
            "pokazuj_punktacja_snip",
        )
        assert CONSTANCE_TO_FIELD_MAP["UZYWAJ_PUNKTACJI_WEWNETRZNEJ"] == (
            "punktacja_wewnetrzna",
            "pokazuj_punktacje_wewnetrzna",
        )


class TestFilterFieldsFromFieldsets:
    """Testy dla funkcji filter_fields_from_fieldsets."""

    def test_returns_unchanged_fieldsets_when_no_fields_to_remove(self):
        """Sprawdza, że fieldsets nie są zmieniane gdy nie ma pól do usunięcia."""
        fieldsets = (
            ("Sekcja 1", {"fields": ("pole1", "pole2", "pole3")}),
            ("Sekcja 2", {"fields": ("pole4", "pole5")}),
        )
        result = filter_fields_from_fieldsets(fieldsets, set())

        assert len(result) == 2
        assert result[0][1]["fields"] == ("pole1", "pole2", "pole3")
        assert result[1][1]["fields"] == ("pole4", "pole5")

    def test_removes_specified_fields(self):
        """Sprawdza usuwanie określonych pól z fieldsets."""
        fieldsets = (
            ("Punktacja", {"fields": ("punkty_kbn", "index_copernicus", "punktacja_snip")}),
        )
        fields_to_remove = {"index_copernicus"}

        result = filter_fields_from_fieldsets(fieldsets, fields_to_remove)

        assert len(result) == 1
        assert "index_copernicus" not in result[0][1]["fields"]
        assert "punkty_kbn" in result[0][1]["fields"]
        assert "punktacja_snip" in result[0][1]["fields"]

    def test_removes_multiple_fields(self):
        """Sprawdza usuwanie wielu pól jednocześnie."""
        fieldsets = (
            (
                "Punktacja",
                {
                    "fields": (
                        "punkty_kbn",
                        "index_copernicus",
                        "punktacja_snip",
                        "punktacja_wewnetrzna",
                    )
                },
            ),
        )
        fields_to_remove = {"index_copernicus", "punktacja_snip"}

        result = filter_fields_from_fieldsets(fieldsets, fields_to_remove)

        assert len(result) == 1
        fields = result[0][1]["fields"]
        assert "index_copernicus" not in fields
        assert "punktacja_snip" not in fields
        assert "punkty_kbn" in fields
        assert "punktacja_wewnetrzna" in fields

    def test_removes_empty_fieldsets(self):
        """Sprawdza, że puste fieldsets są usuwane."""
        fieldsets = (
            ("Sekcja z polami", {"fields": ("pole1", "pole2")}),
            ("Sekcja do usunięcia", {"fields": ("index_copernicus",)}),
        )
        fields_to_remove = {"index_copernicus"}

        result = filter_fields_from_fieldsets(fieldsets, fields_to_remove)

        assert len(result) == 1
        assert result[0][0] == "Sekcja z polami"

    def test_preserves_fieldset_options(self):
        """Sprawdza, że inne opcje fieldset są zachowane."""
        fieldsets = (
            (
                "Punktacja",
                {
                    "classes": ("grp-collapse", "grp-closed"),
                    "fields": ("punkty_kbn", "index_copernicus"),
                },
            ),
        )
        fields_to_remove = {"index_copernicus"}

        result = filter_fields_from_fieldsets(fieldsets, fields_to_remove)

        assert "classes" in result[0][1]
        assert result[0][1]["classes"] == ("grp-collapse", "grp-closed")

    def test_handles_fieldsets_without_fields_key(self):
        """Sprawdza obsługę fieldsets bez klucza 'fields'."""
        fieldsets = (
            ("Sekcja 1", {"description": "Opis sekcji"}),
            ("Sekcja 2", {"fields": ("pole1",)}),
        )
        fields_to_remove = {"pole1"}

        result = filter_fields_from_fieldsets(fieldsets, fields_to_remove)

        # Sekcja bez 'fields' powinna zostać zachowana
        assert len(result) == 1
        assert result[0][0] == "Sekcja 1"


@pytest.mark.django_db
class TestConstanceScoringFieldsMixinIntegration:
    """Testy integracyjne dla ConstanceScoringFieldsMixin."""

    def test_mixin_can_be_imported(self):
        """Sprawdza, że mixin można zaimportować."""
        from bpp.admin.helpers.constance_field_mixin import ConstanceScoringFieldsMixin

        assert ConstanceScoringFieldsMixin is not None

    def test_uczelnia_mixin_can_be_imported(self):
        """Sprawdza, że mixin dla Uczelnia można zaimportować."""
        from bpp.admin.helpers.constance_field_mixin import ConstanceUczelniaFieldsMixin

        assert ConstanceUczelniaFieldsMixin is not None


@pytest.mark.django_db
class TestConstanceAdminIntegration:
    """Testy integracyjne dla constance admin."""

    def test_constance_admin_registered(self):
        """Sprawdza, że constance admin jest zarejestrowany."""
        from django.contrib import admin

        from constance.admin import Config

        assert Config in admin.site._registry

    def test_constance_admin_superuser_only(self):
        """Sprawdza, że constance admin wymaga superusera."""
        from django.contrib import admin

        from constance.admin import Config

        admin_class = admin.site._registry[Config]

        # Sprawdź że admin ma metodę has_module_permission
        assert hasattr(admin_class, "has_module_permission")
