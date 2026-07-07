import re
from decimal import Decimal

# math.isnan zamiast numpy.isnan: ten moduł jest importowany tranzytywnie przez
# modele/admin BPP (np. bpp.models.dyscyplina_naukowa), więc eager ``from numpy
# import isnan`` wciągał całe numpy (~30 MB RSS) do KAŻDEGO procesu na etapie
# ``django.setup()`` — tylko po to, by sprawdzić NaN jednego skalara w
# ``normalize_nulldecimalfield``. math.isnan przyjmuje float i typy z
# ``__float__`` (w tym numpy scalary), a następujące dalej ``float(...)`` i tak
# normalizuje numpy.int64 itp. Zero zmian semantyki dla danych z importu xlsx.
from math import isnan

from django.core.exceptions import ValidationError
from pathspec.util import normalize_file

# Słownik konwersji cyfr rzymskich na arabskie
ROMAN_TO_ARABIC = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
}

# Wzorzec dla cyfr rzymskich (I-XX)
# Dopasowuje: I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XIV, XV,
# XVI, XVII, XVIII, XIX, XX
ROMAN_NUMERAL_PATTERN = (
    r"(?:"
    r"XX|XIX|XVIII|XVII|XVI|XV|XIV|XIII|XII|XI|X|"  # 10-20
    r"IX|VIII|VII|VI|V|IV|III|II|I"  # 1-9
    r")"
)

# Wzorzec dla cyfr arabskich lub rzymskich
NUMBER_PATTERN = rf"(?:\d+|{ROMAN_NUMERAL_PATTERN})"

# Wzorce regex do ekstrakcji numeru części z tytułu publikacji
# Każdy wzorzec to krotka: (regex, indeks_grupy_z_numerem)
PART_NUMBER_PATTERNS = [
    # cz. I, cz. II, cz. 1, cz. 2, etc. (case insensitive)
    (re.compile(rf"\b(cz\.?\s*)({NUMBER_PATTERN})\b", re.IGNORECASE), 2),
    # część I, część 1, etc.
    (re.compile(rf"\b(część\s*)({NUMBER_PATTERN})\b", re.IGNORECASE), 2),
    # part I, part 1, etc.
    (re.compile(rf"\b(part\s*)({NUMBER_PATTERN})\b", re.IGNORECASE), 2),
    # tom I, tom 1, etc.
    (re.compile(rf"\b(tom\s*)({NUMBER_PATTERN})\b", re.IGNORECASE), 2),
    # vol. I, vol. 1, etc.
    (re.compile(rf"\b(vol\.?\s*)({NUMBER_PATTERN})\b", re.IGNORECASE), 2),
]


def normalize_part_number(part: str) -> int | None:
    """Konwertuje numer części (rzymski lub arabski) na int.

    Args:
        part: Numer części jako string (np. "II", "3", "IV")

    Returns:
        Numer części jako int lub None jeśli nie można skonwertować
    """
    if part is None:
        return None

    part = part.upper().strip()

    if not part:
        return None

    # Sprawdź czy to cyfra rzymska
    if part in ROMAN_TO_ARABIC:
        return ROMAN_TO_ARABIC[part]

    # Sprawdź czy to cyfra arabska
    try:
        return int(part)
    except ValueError:
        return None


def extract_part_number(title: str) -> tuple[str, int | None]:
    """Wykrywa i ekstraktuje numer części z tytułu publikacji.

    Obsługiwane wzorce:
    - cz. I, cz. II, cz. 1, cz. 2, etc.
    - część I, część 1, etc.
    - part I, part 1, etc.
    - tom I, tom 1, etc.
    - vol. I, vol. 1, etc.

    Args:
        title: Tytuł publikacji

    Returns:
        Krotka (tytuł_bez_numeru_części, znormalizowany_numer_części_lub_None)
        Numer części jest zwracany jako int (np. 2 dla "cz. II" lub "cz. 2")
    """
    if title is None:
        return ("", None)

    for pattern, group_idx in PART_NUMBER_PATTERNS:
        match = pattern.search(title)
        if match:
            part_str = match.group(group_idx)
            part_number = normalize_part_number(part_str)
            if part_number is not None:
                # Usuń dopasowany fragment z tytułu
                title_without_part = pattern.sub("", title).strip()
                # Usuń podwójne spacje które mogły powstać
                while "  " in title_without_part:
                    title_without_part = title_without_part.replace("  ", " ")
                return (title_without_part, part_number)

    return (title, None)


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


def normalize_boolean(s: str | None | bool) -> bool | None:
    if isinstance(s, bool):
        return s

    if not isinstance(s, str):
        return

    s = s.strip().lower()

    if s.lower() in ["tak", "prawda", "true", "t", "p"]:
        return True

    if s in ["false", "nie", "fałsz", "falsz", "f", "n"]:
        return False


def normalize_nullboleanfield(s: str | None | bool) -> bool | None:
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
    return remove_extra_spaces(fix_spaces_before_dots_and_commas(s))


def normalize_nazwa_dyscypliny(s):
    return remove_extra_spaces(fix_spaces_before_dots_and_commas(s))


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

    if len(k) == 4 and k[:2] == "10":
        # 1001 -> 10.1, 1010 -> 10.10
        return f"10.{int(k[2:])}"

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

    # Strip URL query parameters (e.g., ?urlappend=...&jav=VoR&rel=cite-as)
    if "?" in s:
        s = s.split("?")[0]

    return (
        s.lower()
        .replace("http://", "")
        .replace("https://", "")
        .replace("dx.doi.org/", "")
        .replace("doi.org/", "")
    )


# Wzorzec DOI wg ISO 26324 / DOI handbook: prefiks "10." + rejestrant +
# znak "/" + sufiks. Nie próbujemy walidować sufiksu (DOI dopuszcza niemal
# dowolne znaki) — łapiemy najdłuższy sensowny ciąg do pierwszego białego
# znaku, znaku zapytania lub kotwicy (#).
_DOI_IN_TEXT_RE = re.compile(r"10\.\d{4,9}/[^\s?#]+", re.IGNORECASE)


def extract_doi_from_url(s: None | str) -> None | str:
    """Wyłuskaj DOI z dowolnego ciągu (np. adresu URL pracy).

    Zwraca znormalizowany DOI (przez :func:`normalize_doi`), jeśli w
    ``s`` da się rozpoznać wzorzec ``10.xxxx/...``. W przeciwnym razie
    zwraca ``None`` — adres, którego NIE da się zinterpretować jako DOI,
    nie jest błędem; po prostu nie ma DOI do przekazania.

    >>> extract_doi_from_url("https://doi.org/10.1234/abc.def")
    '10.1234/abc.def'
    >>> extract_doi_from_url("https://example.com/papers/123") is None
    True
    >>> extract_doi_from_url(None) is None
    True
    """
    if not s:
        return None

    match = _DOI_IN_TEXT_RE.search(s)
    if match is None:
        return None

    # Obetnij częste „ogony" interpunkcyjne sklejone z DOI w tekście.
    doi = match.group(0).rstrip(".,;)]}>\"'")
    return normalize_doi(doi)


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
        ) from None

    try:
        # float() zeby pozbyc sie np numpy.int64
        return Decimal(float(probably_decimal))
    except TypeError:
        raise ValidationError(
            f"Nie mogę skonwertować liczby w formacie {probably_decimal} na typ Decimal"
        ) from None


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


# Mapowanie polskich znaków diakrytycznych na ASCII
POLISH_DIACRITICS_MAP = {
    "ą": "a",
    "ć": "c",
    "ę": "e",
    "ł": "l",
    "ń": "n",
    "ó": "o",
    "ś": "s",
    "ź": "z",
    "ż": "z",
    "Ą": "A",
    "Ć": "C",
    "Ę": "E",
    "Ł": "L",
    "Ń": "N",
    "Ó": "O",
    "Ś": "S",
    "Ź": "Z",
    "Ż": "Z",
}


def remove_polish_diacritics(s: str) -> str:
    """Usuwa polskie znaki diakrytyczne.

    'Łętowska' -> 'Letowska'
    'Świątek' -> 'Swiatek'
    """
    if s is None:
        return ""
    for polish, ascii_char in POLISH_DIACRITICS_MAP.items():
        s = s.replace(polish, ascii_char)
    return s


def normalize_nazwisko_do_porownania(s: str) -> str:
    """Normalizuje nazwisko do porównania.

    - Usuwa polskie znaki diakrytyczne
    - Zamienia myślniki na spacje
    - Lowercase
    - Usuwa nadmiarowe spacje

    'Lech-Marańda' -> 'lech maranda'
    'Łętowska' -> 'letowska'
    """
    if s is None:
        return ""
    s = remove_polish_diacritics(s)
    s = s.lower()
    s = s.replace("-", " ")
    return remove_extra_spaces(s)


# Klastry typowych par/trójek imion polsko-angielskich.
# Każdy klaster zawiera wszystkie nawzajem-wymienne pisownie w postaci
# ASCII-lowercase (porównanie odbywa się po unidecode-fold + lowercase).
# Imię może należeć do co najwyżej jednego klastra.
POLISH_ENGLISH_NAME_CLUSTERS: tuple[frozenset[str], ...] = (
    # Mężczyźni
    frozenset({"jan", "john"}),
    frozenset({"krzysztof", "christopher"}),
    frozenset({"pawel", "paul"}),
    frozenset({"piotr", "peter"}),
    frozenset({"michal", "michael"}),
    frozenset({"lukasz", "luke", "lucas"}),
    frozenset({"tomasz", "thomas"}),
    frozenset({"marek", "mark"}),
    frozenset({"andrzej", "andrew"}),
    frozenset({"stefan", "stephen", "steven"}),
    frozenset({"jozef", "joseph"}),
    frozenset({"mikolaj", "nicholas"}),
    frozenset({"jakub", "jacob"}),
    # Kobiety
    frozenset({"maria", "mary"}),
    frozenset({"anna", "ann", "anne"}),
    frozenset({"katarzyna", "catherine", "katherine"}),
    frozenset({"malgorzata", "margaret"}),
    frozenset({"elzbieta", "elizabeth"}),
    frozenset({"ewa", "eve"}),
    frozenset({"magdalena", "madeleine"}),
    frozenset({"aleksandra", "alexandra"}),
    frozenset({"aleksander", "alexander"}),
    frozenset({"helena", "helen"}),
    frozenset({"teresa", "theresa"}),
    frozenset({"dorota", "dorothy"}),
)


def polish_english_first_name_variants(imie: str | None) -> set[str]:
    """Zwraca warianty pisowni imienia między polskim a angielskim.

    Dwa źródła wariantów:

    1. Reguła ``v↔w`` po unidecode-fold (Eva↔Ewa, Viktor↔Wiktor,
       Wioletta↔Violetta) — fonetyczna, generyczna.
    2. Mapa klastrów ``POLISH_ENGLISH_NAME_CLUSTERS`` dla typowych
       par (Krzysztof↔Christopher, Paweł↔Paul, Maria↔Mary itp.) —
       hand-curated, dotyczy imion bez wspólnego fonetycznego korzenia.

    Zwraca zbiór wariantów obejmujący oryginalną pisownię oraz wszystkie
    znormalizowane formy. Nigdy nie modyfikuje nazwisk — tam ``w`` jest
    często autentyczną literą polską (``Wojciechowski`` ≠
    ``Vojciechowski``).
    """
    if not imie:
        return set()
    imie = imie.strip()
    if not imie:
        return set()

    variants = {imie}
    # Reguła v↔w działa na ASCII-fold (żeby Łukasz dał Lukasz, etc.)
    folded = remove_polish_diacritics(imie)
    variants.add(folded)

    for src, dst in (("v", "w"), ("V", "W"), ("w", "v"), ("W", "V")):
        if src in folded:
            variants.add(folded.replace(src, dst))

    # Hand-curated klastry PL↔EN
    folded_lower = folded.lower()
    for cluster in POLISH_ENGLISH_NAME_CLUSTERS:
        if folded_lower in cluster:
            variants.update(cluster)
            break

    return variants
