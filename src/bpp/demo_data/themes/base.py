"""Theme — paczka treści dla generatora demo data (dane, zero logiki).

Pola flavorowane są wymagane; pola strukturalne (prefiksy jednostek/źródeł,
szablony tytułów) mają domyślne = stałe SHARED_*. `kw_only=True` pozwala
mieszać pola z domyślną i bez domyślnej w dowolnej kolejności.
"""

from __future__ import annotations

from dataclasses import dataclass

SHARED_JEDNOSTKA_PREFIKSY: tuple[str, ...] = (
    "Katedra",
    "Zakład",
    "Klinika",
    "Katedra i Klinika",
    "Katedra i Zakład",
    "Instytut",
    "Pracownia",
)

SHARED_ZRODLO_PREFIKSY: tuple[str, ...] = (
    "Acta",
    "Annales",
    "Folia",
    "Roczniki",
    "Przegląd",
    "Zeszyty Naukowe",
    "Studia",
)

SHARED_TYTUL_TEMPLATES: tuple[str, ...] = (
    "Analiza wpływu {topic} na {subject} w {context}",
    "Badania {topic} w kontekście {subject}",
    "Wpływ {topic} na {subject}",
    "{topic}: studium przypadku {subject}",
    "Metodologia {topic} w {context}",
    "Modelowanie {topic} z wykorzystaniem {subject}",
    "Perspektywy rozwoju {topic} w {context}",
    "{topic} jako narzędzie {subject}",
    "Optymalizacja {topic} w {context}",
    "Przegląd literatury: {topic} a {subject}",
)


@dataclass(frozen=True, kw_only=True)
class Theme:
    key: str
    label: str
    # Uczelnia (singleton — bierzemy [0] deterministycznie):
    uczelnia_nazwy: tuple[str, ...]
    uczelnia_skrot: str
    # Wydział: "Wydział <dziedzina>"
    wydzial_dziedziny: tuple[str, ...]
    # Jednostka: "<prefiks> <dziedzina>"
    jednostka_dziedziny: tuple[str, ...]
    # Autor: "<imiona> <nazwisko>"
    autor_imiona: tuple[str, ...]
    autor_nazwiska: tuple[str, ...]
    # Źródło: "<prefiks> <human>"
    zrodlo_human: tuple[str, ...]
    # Wydawcy: pełne nazwy
    wydawcy: tuple[str, ...]
    # Tytuły:
    tytul_topics: tuple[str, ...]
    tytul_subjects: tuple[str, ...]
    tytul_contexts: tuple[str, ...]
    # Streszczenia ({topic}/{subject}/{context} z pól tytułowych):
    streszczenie_templates: tuple[str, ...]
    # Pola strukturalne z domyślnymi SHARED_*:
    jednostka_prefiksy: tuple[str, ...] = SHARED_JEDNOSTKA_PREFIKSY
    zrodlo_prefiksy: tuple[str, ...] = SHARED_ZRODLO_PREFIKSY
    tytul_templates: tuple[str, ...] = SHARED_TYTUL_TEMPLATES
