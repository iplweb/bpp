"""
Mixin do dynamicznego ukrywania pól w panelu admina na podstawie ustawień constance.

Umożliwia ukrywanie pól punktacji (index_copernicus, punktacja_snip, punktacja_wewnetrzna)
w formularzach edycji publikacji, gdy odpowiednie ustawienia constance są wyłączone.
"""

import copy


def get_constance_scoring_settings():
    """
    Pobiera ustawienia dotyczące widoczności pól punktacji z constance.

    Returns:
        dict: Słownik z ustawieniami widoczności pól
    """
    try:
        from constance import config

        return {
            "POKAZUJ_INDEX_COPERNICUS": config.POKAZUJ_INDEX_COPERNICUS,
            "POKAZUJ_PUNKTACJA_SNIP": config.POKAZUJ_PUNKTACJA_SNIP,
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": config.UZYWAJ_PUNKTACJI_WEWNETRZNEJ,
        }
    except (ImportError, AttributeError):
        # Fallback - wszystkie widoczne
        return {
            "POKAZUJ_INDEX_COPERNICUS": True,
            "POKAZUJ_PUNKTACJA_SNIP": True,
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": True,
        }


# Mapowanie ustawień constance na nazwy pól w modelach
CONSTANCE_TO_FIELD_MAP = {
    "POKAZUJ_INDEX_COPERNICUS": ("index_copernicus", "pokazuj_index_copernicus"),
    "POKAZUJ_PUNKTACJA_SNIP": ("punktacja_snip", "pokazuj_punktacja_snip"),
    "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": (
        "punktacja_wewnetrzna",
        "pokazuj_punktacje_wewnetrzna",
    ),
}


def filter_fields_from_fieldsets(fieldsets, fields_to_remove):
    """
    Usuwa określone pola z definicji fieldsets.

    Args:
        fieldsets: Tuple fieldsets do przefiltrowania
        fields_to_remove: Set nazw pól do usunięcia

    Returns:
        list: Nowa lista fieldsets bez usuniętych pól
    """
    if not fields_to_remove:
        return fieldsets

    new_fieldsets = []
    for name, options in fieldsets:
        new_options = copy.copy(options)
        if "fields" in new_options:
            original_fields = new_options["fields"]
            new_fields = tuple(f for f in original_fields if f not in fields_to_remove)
            if new_fields:
                new_options["fields"] = new_fields
                new_fieldsets.append((name, new_options))
        else:
            new_fieldsets.append((name, new_options))

    return new_fieldsets


class ConstanceScoringFieldsMixin:
    """
    Mixin do dynamicznego ukrywania pól punktacji w adminie publikacji.

    Ukrywa pola index_copernicus, punktacja_snip, punktacja_wewnetrzna
    na podstawie ustawień constance.
    """

    def get_fieldsets(self, request, obj=None):
        """
        Dynamicznie modyfikuje fieldsets, ukrywając pola punktacji
        które są wyłączone w constance.
        """
        fieldsets = super().get_fieldsets(request, obj)
        settings = get_constance_scoring_settings()

        fields_to_remove = set()
        for constance_key, field_names in CONSTANCE_TO_FIELD_MAP.items():
            if not settings.get(constance_key, True):
                # Dodaj pole danych (np. index_copernicus)
                fields_to_remove.add(field_names[0])

        return filter_fields_from_fieldsets(fieldsets, fields_to_remove)


class ConstanceUczelniaFieldsMixin:
    """
    Mixin do dynamicznego ukrywania pól pokazuj_* w adminie Uczelnia.

    Ukrywa pola pokazuj_index_copernicus, pokazuj_punktacja_snip,
    pokazuj_punktacje_wewnetrzna na podstawie ustawień constance.
    """

    def get_fieldsets(self, request, obj=None):
        """
        Dynamicznie modyfikuje fieldsets, ukrywając pola pokazuj_*
        które są zbędne gdy dana punktacja jest globalnie wyłączona.
        """
        fieldsets = super().get_fieldsets(request, obj)
        settings = get_constance_scoring_settings()

        fields_to_remove = set()
        for constance_key, field_names in CONSTANCE_TO_FIELD_MAP.items():
            if not settings.get(constance_key, True):
                # Dodaj pole pokazuj_* (np. pokazuj_index_copernicus)
                fields_to_remove.add(field_names[1])

        return filter_fields_from_fieldsets(fieldsets, fields_to_remove)
