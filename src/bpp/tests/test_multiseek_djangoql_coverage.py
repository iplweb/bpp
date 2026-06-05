from multiseek.logic import AUTOCOMPLETE

from bpp.multiseek_registry import registry


def test_every_registry_field_has_translation_path():
    """Każde pole rejestru ma drogę przekładu: metodę to_djangoql LUB
    deklaratywne atrybuty (djangoql_value_field / autocomplete) LUB jest
    bezpośrednim polem skalarnym. Strażnik celu „nic nieprzekładalnego"."""
    missing = []
    for label, field in registry.field_by_name.items():
        has_method = callable(getattr(field, "to_djangoql", None))
        has_value_list = bool(getattr(field, "djangoql_value_field", None))
        is_autocomplete = getattr(field, "type", None) == AUTOCOMPLETE
        has_field_name = bool(getattr(field, "field_name", None))
        if not (has_method or has_value_list or is_autocomplete or has_field_name):
            missing.append(label)
    assert missing == [], f"Pola bez drogi przekładu: {missing}"
