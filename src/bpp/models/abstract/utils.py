"""
Funkcje pomocnicze i fabryki pól dla modeli abstrakcyjnych.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from .constants import (
    BRAK_PAGINACJI,
    IF_DECIMAL_PLACES,
    IF_MAX_DIGITS,
    ILOSC_ZNAKOW_NA_ARKUSZ,
    alt_strony_regex,
    parsed_informacje_regex,
    strony_regex,
)


def get_liczba_arkuszy_wydawniczych(liczba_znakow_wydawniczych):
    return round(liczba_znakow_wydawniczych / ILOSC_ZNAKOW_NA_ARKUSZ, 2)


def nie_zawiera_adresu_doi_org(v):
    if v is None:
        return
    v = v.lower().strip()
    if v.find("doi.org") >= 0:
        raise ValidationError(
            "Pole nie powinno zawierać odnośnika do serwisu doi.org. Identyfikator DOI wpisz "
            "do innego pola. Odnosniki do serwisu DOI, zawierające w swojej tresci numer DOI "
            "są już tworzone przez system. "
        )


def nie_zawiera_http_https(v):
    if v is None:
        return
    v = v.lower().strip()
    if v.startswith("http") or v.startswith("https") or v.find("doi.org") >= 0:
        raise ValidationError(
            "Pole nie powinno zawierać adresu URL (adresu strony WWW) - wpisz tu wyłącznie "
            "identyfikator DOI; lokalizacją położenia rekordu czyli translacją adresu DOI "
            "na adres URL zajmuje się usługa serwisu doi.org i nie ma potrzeby, aby go "
            "tu wpisywać. "
        )


def ImpactFactorField(*args, **kw):
    return models.DecimalField(
        *args,
        max_digits=IF_MAX_DIGITS,
        decimal_places=IF_DECIMAL_PLACES,
        default=Decimal("0.000"),
        **kw,
    )


def wez_zakres_stron(szczegoly):
    """Funkcja wycinająca informacje o stronach z pola 'Szczegóły'"""
    if not szczegoly:
        return

    for bp in BRAK_PAGINACJI:
        if szczegoly.find(bp) >= 0:
            return "brak"

    def ret(res):
        d = res.groupdict()
        if "poczatek" in d and "koniec" in d and d["koniec"] is not None:
            return "{}-{}".format(d["poczatek"], d["koniec"])

        return f"{d['poczatek']}"

    res = strony_regex.search(szczegoly)
    if res is not None:
        return ret(res)

    res = alt_strony_regex.search(szczegoly)
    if res is not None:
        return ret(res)


def parse_informacje_as_dict(
    informacje, parsed_informacje_regex_param=parsed_informacje_regex
):
    """Wycina z pola informacje informację o tomie lub numerze lub roku.

    Jeśli mamy zapis "Vol.60 supl.3" - to "supl.3";
    jeśli mamy zapis "Vol.61 no.2 suppl.2" - to optymalnie byłoby, żeby do pola numeru trafiało "2 suppl.2",
    jeśli zapis jest "Vol.15 no.5 suppl." - "5 suppl."
    """
    if not informacje:
        return {}

    p = parsed_informacje_regex_param.search(informacje)
    if p is not None:
        return p.groupdict()
    return {}


def parse_informacje(informacje, key):
    "Wstecznie kompatybilna wersja funkcji parse_informacje_as_dict"
    return parse_informacje_as_dict(informacje).get(key)
