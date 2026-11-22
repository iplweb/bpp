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

# Przypadki: {topic} — dopełniacz („stresu oksydacyjnego”), {subject} — biernik
# jak po „na” („jakość życia”), {context} — miejscownik po „w” („warunkach
# polowych”).
SHARED_TYTUL_TEMPLATES: tuple[str, ...] = (
    "Analiza wpływu {topic} na {subject} w {context}",
    "Wpływ {topic} na {subject}",
    "Badania {topic} w {context}",
    "Rola {topic} w {context}",
    "Metodologia {topic} w {context}",
    "Perspektywy rozwoju {topic} w {context}",
    "Optymalizacja {topic} w {context}",
    "Ocena wpływu {topic} na {subject}",
    "Modelowanie wpływu {topic} na {subject}",
    "Przegląd literatury dotyczącej {topic}",
    "Nowe podejście do badań {topic} w {context}",
    "Analiza porównawcza {topic} w {context}",
    "Czynniki wpływające na {subject} w {context}",
    "Ewolucja {topic} w {context}: przegląd systematyczny",
    "Historia {topic} w {context}",
    "Ilościowa ocena {topic} w {context}",
    "Wybrane aspekty {topic} w {context}",
    "Uwagi o oddziaływaniu {topic} na {subject}",
    "Długoterminowy wpływ {topic} na {subject} w {context}",
    "Między teorią a praktyką: badania {topic} w {context}",
    "Pilotażowe badanie {topic} w {context}",
    "Statystyczna analiza {topic} i jej wpływu na {subject}",
    "Interdyscyplinarne spojrzenie na problem {topic}",
    "Studium przypadku: rola {topic} w {context}",
    "Weryfikacja hipotezy o wpływie {topic} na {subject}",
    "Zmienność {topic} w {context}",
    "Doświadczenia z badań {topic} w {context}",
    "Czy nasilenie {topic} wpływa na {subject}? Wyniki badań w {context}",
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
    # Autorzy (imiona, nazwisko) tworzeni zawsze jako pierwsi (i nigdy
    # losowani drugi raz) — skrypty zrzutów ekranu do dokumentacji
    # odwołują się do nich po nazwisku:
    autorzy_obowiazkowi: tuple[tuple[str, str], ...] = ()
