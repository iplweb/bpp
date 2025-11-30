"""
Stale i wzorce regex dla modeli abstrakcyjnych.
"""

import re

from django.core.validators import URLValidator

ILOSC_ZNAKOW_NA_ARKUSZ = 40000.0

IF_MAX_DIGITS = 6
IF_DECIMAL_PLACES = 3

BRAK_PAGINACJI = ("[b. pag.]", "[b.pag.]", "[b. pag]", "[b. bag.]")

url_validator = URLValidator()

strony_regex = re.compile(
    r"(?P<parametr>s{1,2}\.)\s*"
    r"(?P<poczatek>(\w*\d+|\w+|\d+))"
    r"((-)(?P<koniec>(\w*\d+|\w+|\d+))|)",
    flags=re.IGNORECASE,
)

alt_strony_regex = re.compile(
    r"(?P<poczatek>\d+)(-(?P<koniec>\d+)|)(\s*s.|)", flags=re.IGNORECASE
)

parsed_informacje_regex = re.compile(
    r"(\[online\])?\s*"
    r"(?P<rok>\d\d+)"
    r"(\s*(vol|t|r|bd)\.*\s*\[?(?P<tom>[A-Za-z]?\d+)\]?)?"
    # To poniżej to była kiedyś jedna długa linia
    r"(\s*(iss|nr|z|h|no)?\.*\s*(?P<numer>((\d+\w*([\/-]\d*\w*)?)\s*((e-)?(suppl|supl)?\.?(\s*\d+|\w+)?)|"
    r"((e-)?(suppl|supl)?\.?\s*\d+(\/\d+)?)|(\d+\w*([\/-]\d*\w*)?))|\[?(suppl|supl)\.\]?))?",
    flags=re.IGNORECASE,
)
