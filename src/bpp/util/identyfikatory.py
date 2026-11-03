"""Identyfikatory zewnętrznych profili autora: WoS, Scopus, Google Scholar.

Trzymamy same identyfikatory (nie URL-e) — linki budujemy z szablonów, jak
dla ORCID. Użytkownicy zwykle wklejają cały adres profilu, więc normalizatory
wyciągają z niego identyfikator. Wartość nierozpoznana zostaje bez zmian i
odrzuca ją walidator pola modelu (komunikat zamiast cichego zgadywania).
"""

import re

from django.core.validators import MaxLengthValidator, RegexValidator

# ResearcherID (np. ``A-1234-2008``) albo numeryczny identyfikator rekordu
# autora w nowym interfejsie WoS (``/wos/author/record/1234567``).
WOS_RESEARCHERID_RE = r"^([A-Z]{1,3}-\d{4}-\d{4}|\d{5,12})$"
SCOPUS_AUTHOR_ID_RE = r"^\d{6,15}$"
GOOGLE_SCHOLAR_ID_RE = r"^[A-Za-z0-9_-]{12}$"

WOS_URL = "https://www.webofscience.com/wos/author/record/{}"
SCOPUS_URL = "https://www.scopus.com/authid/detail.uri?authorId={}"
GOOGLE_SCHOLAR_URL = "https://scholar.google.com/citations?user={}"

wos_researcherid_validator = RegexValidator(
    WOS_RESEARCHERID_RE,
    "ResearcherID ma postać np. A-1234-2008 (albo numer rekordu autora w WoS).",
    code="wos_researcherid_invalid_format",
)
scopus_author_id_validator = RegexValidator(
    SCOPUS_AUTHOR_ID_RE,
    "Scopus Author ID to sam ciąg cyfr, np. 7004212771.",
    code="scopus_author_id_invalid_format",
)
google_scholar_id_validator = RegexValidator(
    GOOGLE_SCHOLAR_ID_RE,
    "Identyfikator Google Scholar to 12 znaków z parametru „user=” adresu "
    "profilu, np. qc6CJjYAAAAJ.",
    code="google_scholar_id_invalid_format",
)

_WOS_W_TEKSCIE = re.compile(r"(?:^|/)([A-Z]{1,3}-\d{4}-\d{4})(?:$|[/?#])")
_WOS_REKORD_W_URL = re.compile(r"/author/record/(\d{5,12})(?:$|[/?#])")
_SCOPUS_W_URL = re.compile(r"[?&]authorId=(\d+)", re.IGNORECASE)
_SCHOLAR_W_URL = re.compile(r"[?&]user=([A-Za-z0-9_-]{12})(?:$|&)")


def _oczysc(wartosc):
    return (wartosc or "").strip()


def normalizuj_wos_researcherid(wartosc):
    wartosc = _oczysc(wartosc)
    if not wartosc:
        return ""
    if m := _WOS_W_TEKSCIE.search(wartosc.upper()):
        return m.group(1)
    if m := _WOS_REKORD_W_URL.search(wartosc):
        return m.group(1)
    return wartosc


def normalizuj_scopus_author_id(wartosc):
    wartosc = _oczysc(wartosc)
    if m := _SCOPUS_W_URL.search(wartosc):
        return m.group(1)
    return wartosc


def normalizuj_google_scholar_id(wartosc):
    wartosc = _oczysc(wartosc)
    if m := _SCHOLAR_W_URL.search(wartosc):
        return m.group(1)
    return wartosc


class IdentyfikatoryProfiliFormMixin:
    """``clean_<pole>`` dla ModelForm autora: wyciąga ID z wklejonego URL-a.

    Walidacja formatu odbywa się potem w walidatorach pól modelu
    (``_post_clean`` → ``full_clean``).
    """

    POLA_Z_URL = ("wos_researcherid", "scopus_author_id", "google_scholar_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pole formularza dziedziczy max_length z modelu i odrzuciłoby wklejony
        # adres profilu, zanim ``clean_<pole>`` wyciągnie z niego ID. Długość
        # po normalizacji i tak sprawdzają walidatory modelu.
        for nazwa in self.POLA_Z_URL:
            pole = self.fields.get(nazwa)
            if pole is None:
                continue
            pole.max_length = None
            pole.validators = [
                v for v in pole.validators if not isinstance(v, MaxLengthValidator)
            ]
            pole.widget.attrs.pop("maxlength", None)

    def clean_wos_researcherid(self):
        return normalizuj_wos_researcherid(self.cleaned_data.get("wos_researcherid"))

    def clean_scopus_author_id(self):
        return normalizuj_scopus_author_id(self.cleaned_data.get("scopus_author_id"))

    def clean_google_scholar_id(self):
        return normalizuj_google_scholar_id(self.cleaned_data.get("google_scholar_id"))
