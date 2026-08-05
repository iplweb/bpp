"""Motyw 'disney' — klasyczne postacie Disneya (placeholdery demo)."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme

DISNEY = Theme(
    key="disney",
    label="Disney",
    uczelnia_nazwy=(
        "Uniwersytet Disneya",
        "Akademia Magicznego Królestwa",
    ),
    uczelnia_skrot="UMK",
    wydzial_dziedziny=(
        "Animacji",
        "Magii Królestwa",
        "Przygód",
        "Baśni",
        "Muzyki",
    ),
    jednostka_dziedziny=(
        "Animacji Klasycznej",
        "Magii Królestwa",
        "Baśni Porównawczych",
        "Przygód Morskich",
        "Latających Dywanów",
        "Pieśni i Tańca",
    ),
    autor_imiona=(
        # Bohaterowie:
        "Miki",
        "Donald",
        "Sknerus",
        "Goofy",
        "Pluto",
        "Daisy",
        "Elsa",
        "Anna",
        "Ariel",
        "Belle",
        "Mulan",
        "Simba",
        "Aladyn",
        # Czarne charaktery (złoczyńcy Disneya):
        "Jafar",
        "Skaza",
        "Urszula",
        "Cruella",
        "Hades",
        "Gaston",
        "Diabolina",
        "Hak",
    ),
    # nazwiska NIGDY puste — jednoimienne postacie dostają przydomek:
    autor_nazwiska=(
        # Przydomki bohaterów:
        "Mysz",
        "Kaczor",
        "McKwacz",
        "z Arendelle",
        "Syrenka",
        "Lew",
        "z Krainy Lodu",
        "z Agrabah",
        # Przydomki czarnych charakterów:
        "de Mon",
        "Władca Podziemi",
        "Wielki Wezyr",
        "z Wyspy Czaszki",
        "Uzurpator",
        "Morska Wiedźma",
    ),
    zrodlo_human=(
        "Magicznego Królestwa",
        "Disnejowskie",
        "Animowane",
        "Baśniowe",
    ),
    wydawcy=(
        "Disney Academic Press",
        "Wydawnictwo Magicznego Królestwa",
        "Oficyna Myszki Miki",
        "Dom Wydawniczy Arendelle",
    ),
    tytul_topics=(
        "animacji klasycznej",
        "magii królestwa",
        "baśni",
        "przygód morskich",
        "pieśni królestwa",
        "latających dywanów",
    ),
    tytul_subjects=(
        "skuteczność czaru",
        "trwałość magii",
        "siłę przyjaźni",
        "tempo animacji",
        "rozpoznawalność postaci",
    ),
    tytul_contexts=(
        "warunkach królestwa",
        "zamku Arendelle",
        "podwodnym świecie",
        "studiu animacji",
        "magicznej krainie",
    ),
    streszczenie_templates=(
        "Zbadano wpływ {topic} na {subject}.",
        "Badanie przeprowadzono w {context}.",
        "Wyniki ukazują związek {topic} z {subject}.",
        "Bohaterowie królestwa wykazali rolę {topic} dla {subject}.",
        "Obserwacje w {context} potwierdzają znaczenie {topic}.",
    ),
)
