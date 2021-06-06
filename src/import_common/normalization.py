from typing import Union


def remove_extra_spaces(s: str) -> str:
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.strip()
    return s


def normalize_nullboleanfield(s: Union[str, None, bool]) -> Union[bool, None]:
    if isinstance(s, bool):
        return s
    if s is None:
        return
    s = s.strip().lower()

    if s in ["true", "tak", "prawda", "t", "p"]:
        return True
    if s in ["false", "nie", "fałsz", "falsz", "f", "n"]:
        return False


def normalize_skrot(s):
    return remove_extra_spaces(s.lower().replace(" .", ". "))


def normalize_tytul_naukowy(s):
    return normalize_skrot(s)


def normalize_tytul_publikacji(s):
    return normalize_skrot(s)


def normalize_funkcja_autora(s: str) -> str:
    return normalize_skrot(s).lower()


def normalize_grupa_pracownicza(s: str):
    return normalize_skrot(s)


def normalize_wymiar_etatu(s: str):
    return normalize_skrot(s)


def normalize_nazwa_jednostki(s: str) -> str:
    return remove_extra_spaces(s.strip())


def normalize_nazwa_wydawcy(s: str) -> str:
    return remove_extra_spaces(s.strip())


def normalize_exception_reason(s: str) -> str:
    return remove_extra_spaces(s.replace("\n", " ").replace("\r\n", " "))


def normalize_tytul_zrodla(s):
    return normalize_skrot(s)


def normalize_nazwa_dyscypliny(s):
    return normalize_skrot(s)


def normalize_kod_dyscypliny(k):
    if k is None:
        return None

    if k.endswith("_0"):
        k = k[:-2]
        return f"{k[0]}.{int(k[1:])}"
    if k.find(".") >= 0:
        return k
    return f"{k[0]}.{int(k[1:])}"
