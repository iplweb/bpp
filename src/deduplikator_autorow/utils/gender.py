"""
Funkcje zgadywania płci na podstawie imienia.
"""

from enum import Enum


class Gender(Enum):
    MALE = "M"
    FEMALE = "K"
    UNKNOWN = "?"


# Męskie imiona kończące się na -a (wyjątki od reguły)
MESKIE_IMIONA_NA_A = frozenset(
    [
        "kuba",
        "barnaba",
        "bonawentura",
        "kosma",
        "dyzma",
        "nikita",
        "sasza",
        "ilja",
        "boryna",
        "juda",
        "kosiba",
        "jarema",
        "passa",  # zdrobnienie
        "mustafa",
        "joshua",
        "luka",
        "ilya",
        "aissa",
        "mateusza",  # błędna forma
        "mustaffa",
    ]
)

# Kobiece imiona NIE kończące się na -a (wyjątki od reguły)
ZENSKIE_IMIONA_BEZ_A = frozenset(
    [
        "miriam",
        "ruth",
        "esther",
        "noemi",
        "rachel",
        "carmen",
        "ines",
        "dolores",
        "beatrix",
        "agnes",
        "ingrid",
        "astrid",
        "gudrun",
        "margit",
        "elin",
        "noor",
        "nicole",  # może być też z -a
    ]
)


def zgadnij_plec_po_imieniu(imie: str) -> Gender:
    """
    Zgaduje płeć na podstawie imienia (polskie konwencje).

    W języku polskim:
    - Imiona kobiece zazwyczaj kończą się na -a (Anna, Maria, Teresa)
    - Imiona męskie kończą się na spółgłoskę lub -y, -o, -i (Jan, Piotr, Jerzy)

    Args:
        imie: Pojedyncze imię do analizy

    Returns:
        Gender: MALE, FEMALE lub UNKNOWN jeśli nie można określić
    """
    if not imie:
        return Gender.UNKNOWN

    # Wyczyść i znormalizuj
    imie_clean = imie.strip().lower()

    # Usuń ewentualną kropkę (inicjały)
    if imie_clean.endswith("."):
        imie_clean = imie_clean[:-1]

    # Jeśli to tylko inicjał (1 znak) - nie możemy określić
    if len(imie_clean) <= 1:
        return Gender.UNKNOWN

    # Sprawdź wyjątki najpierw
    if imie_clean in MESKIE_IMIONA_NA_A:
        return Gender.MALE

    if imie_clean in ZENSKIE_IMIONA_BEZ_A:
        return Gender.FEMALE

    # Reguła ogólna: końcówka -a = kobieta (w polskim)
    if imie_clean.endswith("a"):
        return Gender.FEMALE

    # Końcówki typowo męskie
    # Spółgłoski, -y, -o, -i (ale -i jest rzadkie)
    return Gender.MALE


def zgadnij_plec_autora(imiona: str, plec_z_bazy=None) -> Gender:
    """
    Zgaduje płeć autora na podstawie imion lub pola plec z bazy.

    Priorytet:
    1. Jeśli plec_z_bazy jest wypełnione - używamy go
    2. Jeśli nie - zgadujemy po pierwszym imieniu

    Args:
        imiona: String z imionami autora (może być wiele, np. "Jan Kazimierz")
        plec_z_bazy: Obiekt Plec z bazy danych (może być None)

    Returns:
        Gender: MALE, FEMALE lub UNKNOWN
    """
    # Priorytet 1: dane z bazy
    if plec_z_bazy:
        skrot = getattr(plec_z_bazy, "skrot", "").upper()
        nazwa = getattr(plec_z_bazy, "nazwa", "").lower()

        if skrot == "M" or "męż" in nazwa or "meż" in nazwa:
            return Gender.MALE
        if skrot == "K" or "kob" in nazwa or "żeń" in nazwa or "zen" in nazwa:
            return Gender.FEMALE

    # Priorytet 2: zgaduj po pierwszym imieniu
    if imiona:
        # Weź pierwsze imię (przed spacją)
        pierwsze_imie = imiona.split()[0] if imiona.strip() else ""
        return zgadnij_plec_po_imieniu(pierwsze_imie)

    return Gender.UNKNOWN


def plcie_sa_rozne(gender1: Gender, gender2: Gender) -> bool:
    """
    Sprawdza czy dwie płcie są PEWNIE różne.

    Zwraca True tylko jeśli:
    - Jedna jest MALE, druga FEMALE (różne płcie)

    Zwraca False jeśli:
    - Przynajmniej jedna jest UNKNOWN (nie możemy być pewni)
    - Obie są takie same

    Args:
        gender1: Pierwsza płeć
        gender2: Druga płeć

    Returns:
        bool: True jeśli płcie są na pewno różne
    """
    if gender1 == Gender.UNKNOWN or gender2 == Gender.UNKNOWN:
        return False

    return gender1 != gender2
