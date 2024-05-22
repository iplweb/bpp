from decimal import Decimal
from typing import Union

from django.core.exceptions import ValidationError
from numpy import isnan
from pathspec.util import normalize_file


def remove_trailing_interpunction(s: str) -> str:
    try:
        while s[-1] in ".,-":
            s = s[:-1]
    except IndexError:
        return ""

    return s


def remove_extra_spaces(s: str) -> str:
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.strip()
    return s


def fix_spaces_before_dots_and_commas(s: str) -> str:
    while s.find(" .") >= 0 or s.find(" ,") >= 0:
        s = s.replace(" .", ". ").replace(" ,", ", ")
    return s


def normalize_first_name(s: str) -> str | None:
    if not isinstance(s, str) or s is None or s == "" or not s:
        return
    return remove_extra_spaces(s)


normalize_last_name = normalize_first_name
normalize_publisher = normalize_first_name


def normalize_boolean(s: Union[str, None, bool]) -> Union[bool, None]:
    if isinstance(s, bool):
        return s

    if not isinstance(s, str):
        return

    s = s.strip().lower()

    if s.lower() in ["tak", "prawda", "true", "t", "p"]:
        return True

    if s in ["false", "nie", "fałsz", "falsz", "f", "n"]:
        return False


def normalize_nullboleanfield(s: Union[str, None, bool]) -> Union[bool, None]:
    return normalize_boolean(s)


def normalize_skrot(s):
    if s is None:
        return
    return remove_extra_spaces(fix_spaces_before_dots_and_commas(s.lower()))


def normalize_tytul_naukowy(s):
    return normalize_skrot(s)


def normalize_title(s: str) -> str | None:
    if s is None or not s:
        return
    return remove_extra_spaces(s)


ONLINE_STR = "[online]"


def normalize_tytul_publikacji(s):
    if s is None:
        return
    ret = remove_trailing_interpunction(
        remove_extra_spaces(fix_spaces_before_dots_and_commas(s))
    )
    if ret.endswith(ONLINE_STR):
        ret = ret[: -len(ONLINE_STR)].strip()
    ret = ret.replace("\r", " ").replace("\n", " ")
    return remove_extra_spaces(ret)


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


def normalize_isbn(isbn: str) -> str | None:
    if isbn is None or not isinstance(isbn, str) or not isbn:
        return

    return isbn.replace(".", "").replace("-", "").replace(" ", "").strip()


normalize_issn = normalize_isbn


def normalize_kod_dyscypliny(k):
    if k is None:
        return None

    if k.endswith("_0"):
        k = k[:-2]
        return f"{k[0]}.{int(k[1:])}"
    if k.find(".") >= 0:
        return k
    return f"{k[0]}.{int(k[1:])}"


def normalize_public_uri(public_uri):
    if public_uri is not None:
        return public_uri.strip()


def normalize_doi(s: str) -> None | str:
    """
    https://www.doi.org/doi_handbook/2_Numbering.html#2.4
    """

    if s is None:
        return

    s = s.strip()

    if not s:
        return

    return (
        s.lower()
        .replace("http://", "")
        .replace("https://", "")
        .replace("dx.doi.org/", "")
        .replace("doi.org/", "")
    )


def normalize_filename(s: str) -> str:
    s = normalize_file(s).replace(" ", "_").replace(",", "_")

    while s.find("__") != -1:
        s = s.replace("__", "_")
    return s


def normalize_orcid(s: str) -> str | None:
    if not isinstance(s, str) or s is None or s == "" or not s:
        return
    return (
        s.strip()
        .lower()
        .replace("http://orcid.org/", "")
        .replace("https://orcid.org/", "")
        .upper()
    )


def normalize_nulldecimalfield(probably_decimal):
    if probably_decimal is None:
        return

    try:
        if probably_decimal is not None and isnan(probably_decimal):
            return
    except TypeError:
        raise ValidationError(
            f"Nie mogę skonwertować liczby w formacie {probably_decimal} na typ Decimal"
        )

    try:
        # float() zeby pozbyc sie np numpy.int64
        return Decimal(float(probably_decimal))
    except TypeError:
        raise ValidationError(
            f"Nie mogę skonwertować liczby w formacie {probably_decimal} na typ Decimal"
        )


def normalize_oplaty_za_publikacje(
    rekord,
    opl_pub_cost_free,
    opl_pub_research_potential,
    opl_pub_research_or_development_projects,
    opl_pub_other,
    opl_pub_amount,
):
    # Publikacja bezkosztowa
    rekord.opl_pub_cost_free = False
    if normalize_boolean(opl_pub_cost_free):
        rekord.opl_pub_cost_free = True

    # Środki finansowe o których mowa w artykule 365
    rekord.opl_pub_research_potential = False
    if normalize_boolean(opl_pub_research_potential):
        rekord.opl_pub_research_potential = True

    # Środki finansowe na realizację projektu
    rekord.opl_pub_research_or_development_projects = False
    if normalize_boolean(opl_pub_research_or_development_projects):
        rekord.opl_pub_research_or_development_projects = True

    # Inne srodki finansowe
    rekord.opl_pub_other = False
    if normalize_boolean(opl_pub_other):
        rekord.opl_pub_other = True

    # Kwota
    rekord.opl_pub_amount = normalize_nulldecimalfield(opl_pub_amount)

    rekord.clean()


def normalize_rekord_id(rekord_id):
    """Normalizuje z postaci (43, 43) do {43,43} zeby mozna odpytac baze dancyh."""
    if not isinstance(rekord_id, str):
        return

    if rekord_id is None:
        return

    if not rekord_id:
        return

    ret = rekord_id.replace("(", "{").replace(")", "}").strip()
    if not ret.startswith("{"):
        ret = "{" + ret
    if not ret.endswith("}"):
        ret += "}"

    return ret
