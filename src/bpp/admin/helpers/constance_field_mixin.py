"""
Mixin do dynamicznego ukrywania pól w panelu admina na podstawie ustawień uczelni.

Umożliwia ukrywanie pól punktacji (index_copernicus, punktacja_snip, punktacja_wewnetrzna)
w formularzach edycji publikacji, gdy odpowiednie ustawienia uczelni są wyłączone.
"""

import copy


def get_scoring_settings(uczelnia=None):
    """
    Pobiera ustawienia dotyczące widoczności pól punktacji z obiektu Uczelnia.

    Args:
        uczelnia: Obiekt Uczelnia (opcjonalny). Jeśli None, zwraca domyślne wartości.

    Returns:
        dict: Słownik z ustawieniami widoczności pól
    """
    if uczelnia is not None:
        return {
            "POKAZUJ_INDEX_COPERNICUS": uczelnia.pokazuj_index_copernicus,
            "POKAZUJ_PUNKTACJA_SNIP": uczelnia.pokazuj_punktacja_snip,
            "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": uczelnia.pokazuj_punktacje_wewnetrzna,
        }
    # Fallback - wszystkie widoczne
    return {
        "POKAZUJ_INDEX_COPERNICUS": True,
        "POKAZUJ_PUNKTACJA_SNIP": True,
        "UZYWAJ_PUNKTACJI_WEWNETRZNEJ": True,
    }


# Backward compatibility alias
get_constance_scoring_settings = get_scoring_settings


# Mapowanie ustawień na nazwy pól w modelach
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
    na podstawie ustawień uczelni.
    """

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        uczelnia = getattr(request, "_uczelnia", None)
        settings = get_scoring_settings(uczelnia)

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
    pokazuj_punktacje_wewnetrzna na podstawie ustawień uczelni.
    """

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        uczelnia = getattr(request, "_uczelnia", None)
        settings = get_scoring_settings(uczelnia)

        fields_to_remove = set()
        for constance_key, field_names in CONSTANCE_TO_FIELD_MAP.items():
            if not settings.get(constance_key, True):
                # Dodaj pole pokazuj_* (np. pokazuj_index_copernicus)
                fields_to_remove.add(field_names[1])

        return filter_fields_from_fieldsets(fieldsets, fields_to_remove)
