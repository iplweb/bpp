"""Domyslny slownik dyscyplin naukowych zgodny z Rozporzadzeniem
Ministra Edukacji i Nauki z 11 pazdziernika 2022 r. (Dz.U. 2022 poz. 2202)
oraz jednolitym tekstem z 12 lutego 2025 r. (Dz.U. 2025 poz. 211).

Pomija dziedziny "Nauki o rodzinie" (id 9) i "Nauki weterynaryjne"
(id 10) — `bpp.const.DZIEDZINY` nie ma dla nich mappingu, wiec
`waliduj_format_kodu_numer` odrzuci kody 9.x i 10.x.

Kody nadane sztucznie w formacie `<id_dziedziny>.<index>` aby pasowac
do validatora; numeracja per-dziedzina od 1, kolejnosc alfabetyczna.

Zrodla:
  - https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20220002202
  - https://pl.wikipedia.org/wiki/Klasyfikacja_dziedzin_i_dyscyplin_naukowych_w_Polsce
"""

from __future__ import annotations

DEFAULT_DYSCYPLINY: tuple[tuple[str, str], ...] = (
    # 1. Nauki humanistyczne
    ("1.1", "archeologia"),
    ("1.2", "etnologia i antropologia kulturowa"),
    ("1.3", "filozofia"),
    ("1.4", "historia"),
    ("1.5", "językoznawstwo"),
    ("1.6", "literaturoznawstwo"),
    ("1.7", "nauki o kulturze i religii"),
    ("1.8", "nauki o sztuce"),
    ("1.9", "polonistyka"),
    # 2. Nauki inżynieryjno-techniczne
    ("2.1", "architektura i urbanistyka"),
    (
        "2.2",
        "automatyka, elektronika, elektrotechnika i technologie kosmiczne",
    ),
    ("2.3", "informatyka techniczna i telekomunikacja"),
    ("2.4", "inżynieria bezpieczeństwa"),
    ("2.5", "inżynieria biomedyczna"),
    ("2.6", "inżynieria chemiczna"),
    ("2.7", "inżynieria lądowa, geodezja i transport"),
    ("2.8", "inżynieria materiałowa"),
    ("2.9", "inżynieria mechaniczna"),
    ("2.10", "inżynieria środowiska, górnictwo i energetyka"),
    ("2.11", "ochrona dziedzictwa i konserwacja zabytków"),
    # 3. Nauki medyczne i o zdrowiu
    ("3.1", "biologia medyczna"),
    ("3.2", "nauki farmaceutyczne"),
    ("3.3", "nauki medyczne"),
    ("3.4", "nauki o kulturze fizycznej"),
    ("3.5", "nauki o zdrowiu"),
    # 4. Nauki rolnicze
    ("4.1", "nauki leśne"),
    ("4.2", "rolnictwo i ogrodnictwo"),
    ("4.3", "technologia żywności i żywienia"),
    ("4.4", "zootechnika i rybactwo"),
    # 5. Nauki społeczne
    ("5.1", "ekonomia i finanse"),
    ("5.2", "geografia społeczno-ekonomiczna i gospodarka przestrzenna"),
    ("5.3", "nauki o bezpieczeństwie"),
    ("5.4", "nauki o komunikacji społecznej i mediach"),
    ("5.5", "nauki o polityce i administracji"),
    ("5.6", "nauki o zarządzaniu i jakości"),
    ("5.7", "nauki prawne"),
    ("5.8", "nauki socjologiczne"),
    ("5.9", "pedagogika"),
    ("5.10", "prawo kanoniczne"),
    ("5.11", "psychologia"),
    ("5.12", "stosunki międzynarodowe"),
    # 6. Nauki ścisłe i przyrodnicze
    ("6.1", "astronomia"),
    ("6.2", "biotechnologia"),
    ("6.3", "informatyka"),
    ("6.4", "matematyka"),
    ("6.5", "nauki biologiczne"),
    ("6.6", "nauki chemiczne"),
    ("6.7", "nauki fizyczne"),
    ("6.8", "nauki o Ziemi i środowisku"),
    # 7. Nauki teologiczne
    ("7.1", "nauki biblijne"),
    ("7.2", "nauki teologiczne"),
    # 8. Sztuka
    ("8.1", "sztuki filmowe i teatralne"),
    ("8.2", "sztuki muzyczne"),
    ("8.3", "sztuki plastyczne i konserwacja dzieł sztuki"),
)


def seed_default_dyscypliny(stdout=None) -> tuple[int, int]:
    """Idempotentnie wstawia DEFAULT_DYSCYPLINY do Dyscyplina_Naukowa.

    Lookup po `kod` (unique). Zwraca (created, existed).
    """
    from bpp.models import Dyscyplina_Naukowa

    created = 0
    existed = 0
    for kod, nazwa in DEFAULT_DYSCYPLINY:
        _, was_created = Dyscyplina_Naukowa.objects.get_or_create(
            kod=kod,
            defaults={"nazwa": nazwa},
        )
        if was_created:
            created += 1
        else:
            existed += 1

    if stdout is not None:
        stdout.write(
            f"Dyscypliny: utworzone {created}, istniejace {existed}, "
            f"razem {len(DEFAULT_DYSCYPLINY)}.\n"
        )

    return created, existed
