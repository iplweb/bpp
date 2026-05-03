"""Scalanie wyników z wielu ekstraktorów na jeden słownik."""


def _merge_sources(sources: list[dict]) -> dict:
    """Scal wyniki z wielu extractorów.

    Pierwszy niepusty wynik dla każdego pola wygrywa.
    Dla list (authors, keywords) — pierwsza niepusta lista.
    """
    merged = {}
    list_fields = {"authors", "keywords"}

    for source in sources:
        for key, value in source.items():
            if key in merged:
                continue
            if key in list_fields:
                if isinstance(value, list) and value:
                    merged[key] = value
            elif value is not None and value != "":
                merged[key] = value

    return merged
