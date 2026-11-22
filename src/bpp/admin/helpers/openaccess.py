"""Pole „Data udostępnienia (dzień lub miesiąc i rok)” w sekcji OpenAccess.

Freshdesk #281. PBN przyjmuje datę udostępnienia OA jako pełną datę
(``releaseDate``) ALBO miesiąc i rok (``releaseDateMonth`` +
``releaseDateYear``); samego roku nie przyjmuje. W formularzu redaktor
widzi JEDNO pole tekstowe, a formularz rozkłada wpis na pola modelu:

- pełna data → ``openaccess_data_opublikowania``,
- miesiąc i rok → ``openaccess_miesiac_udostepnienia`` +
  ``openaccess_rok_udostepnienia`` (data czyszczona).
"""

import datetime
import re

from django import forms
from django.core.exceptions import ValidationError

POLE_FORMULARZA = "openaccess_data_udostepnienia"

POLE_DATA = "openaccess_data_opublikowania"
POLE_ROK = "openaccess_rok_udostepnienia"
POLE_MIESIAC = "openaccess_miesiac_udostepnienia"
POLA_MODELU = (POLE_DATA, POLE_ROK, POLE_MIESIAC)

ETYKIETA = "OpenAccess: data udostępnienia (dzień lub miesiąc i rok)"

POMOC = (
    "Data udostępnienia pracy w otwartym dostępie, wysyłana do PBN. Wpisz "
    "pełną datę, np. 30.12.2025, 2025-12-30 lub 2025.12.30, albo — gdy dzień "
    "nie jest znany — sam miesiąc i rok, np. 12.2025, 2025-12 lub 2025.12. "
    "Sam rok nie wystarczy: PBN wymaga co najmniej miesiąca i roku. Gdy pole "
    "jest puste, eksport użyje daty dostępu do strony WWW (o ile ją podano); "
    "w przeciwnym razie data udostępnienia nie zostanie wysłana."
)

_SEP = r"[-./]"
_RRRR_MM_DD = re.compile(rf"^(\d{{4}}){_SEP}(\d{{1,2}}){_SEP}(\d{{1,2}})$")
_DD_MM_RRRR = re.compile(rf"^(\d{{1,2}}){_SEP}(\d{{1,2}}){_SEP}(\d{{4}})$")
_RRRR_MM = re.compile(rf"^(\d{{4}}){_SEP}(\d{{1,2}})$")
_MM_RRRR = re.compile(rf"^(\d{{1,2}}){_SEP}(\d{{4}})$")
_RRRR = re.compile(r"^\d{4}$")

KOMUNIKAT_SAM_ROK = (
    "PBN wymaga co najmniej miesiąca i roku udostępnienia — sam rok nie "
    "wystarczy. Wpisz np. 12.{rok} albo pełną datę."
)
KOMUNIKAT_FORMAT = (
    "Nierozpoznany format daty. Wpisz pełną datę (np. 30.12.2025, "
    "2025-12-30) albo miesiąc i rok (np. 12.2025, 2025-12)."
)


def parsuj_date_udostepnienia(tekst):
    """Rozkłada wpis na ``(data, rok, miesiac)``.

    Zwraca ``(date, None, None)`` dla pełnej daty, ``(None, rok, miesiac)``
    dla miesiąca i roku, ``(None, None, None)`` dla pustego wpisu.
    Rzuca ``ValidationError`` dla samego roku i nierozpoznanego formatu.
    """
    tekst = (tekst or "").strip()
    if not tekst:
        return None, None, None

    if _RRRR.match(tekst):
        raise ValidationError(KOMUNIKAT_SAM_ROK.format(rok=tekst))

    pelna = None
    if m := _RRRR_MM_DD.match(tekst):
        pelna = (int(m[1]), int(m[2]), int(m[3]))
    elif m := _DD_MM_RRRR.match(tekst):
        pelna = (int(m[3]), int(m[2]), int(m[1]))
    if pelna is not None:
        try:
            return datetime.date(*pelna), None, None
        except ValueError as err:
            raise ValidationError(f"Data „{tekst}” nie istnieje w kalendarzu.") from err

    if m := _RRRR_MM.match(tekst):
        rok, miesiac = int(m[1]), int(m[2])
    elif m := _MM_RRRR.match(tekst):
        rok, miesiac = int(m[2]), int(m[1])
    else:
        raise ValidationError(KOMUNIKAT_FORMAT)

    if not 1 <= miesiac <= 12:
        raise ValidationError(
            f"Miesiąc {miesiac} jest nieprawidłowy — dopuszczalne wartości to 1–12."
        )
    return None, rok, miesiac


def formatuj_date_udostepnienia(data, rok, miesiac):
    """Wartość pola w spójnym formacie: ``DD.MM.RRRR`` albo ``MM.RRRR``."""
    if data is not None:
        return data.strftime("%d.%m.%Y")
    if rok is not None and miesiac is not None:
        return f"{miesiac:02d}.{rok}"
    if rok is not None:
        # Niekompletne dane (np. sprzed FD#281) — pokaż, co jest, żeby
        # zapis wymusił uzupełnienie miesiąca.
        return str(rok)
    return ""


class OpenAccessDataUdostepnieniaFormMixin(forms.Form):
    """Jedno pole tekstowe zamiast trzech pól modelu (data, miesiąc, rok)."""

    openaccess_data_udostepnienia = forms.CharField(
        label=ETYKIETA,
        help_text=POMOC,
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"class": "bpp-input-narrow"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if POLE_FORMULARZA in self.fields and self.instance is not None:
            self.initial.setdefault(
                POLE_FORMULARZA,
                formatuj_date_udostepnienia(
                    *(getattr(self.instance, pole, None) for pole in POLA_MODELU)
                ),
            )

    def clean_openaccess_data_udostepnienia(self):
        return parsuj_date_udostepnienia(self.cleaned_data.get(POLE_FORMULARZA))

    def _post_clean(self):
        # Przenieś rozłożony wpis na instancję PRZED walidacją modelu
        # (``construct_instance`` nie dotyka pól spoza formularza).
        if POLE_FORMULARZA in self.fields and POLE_FORMULARZA in self.cleaned_data:
            for pole, wartosc in zip(
                POLA_MODELU, self.cleaned_data[POLE_FORMULARZA], strict=True
            ):
                setattr(self.instance, pole, wartosc)
        super()._post_clean()

    def _update_errors(self, errors):
        # Błędy walidacji modelu dla data/miesiąc/rok pokazujemy przy
        # jedynym polu formularza (inaczej Django rzuci ValueError, bo tych
        # pól modelu nie ma w formularzu).
        if POLE_FORMULARZA in self.fields and hasattr(errors, "error_dict"):
            przeniesione = []
            for pole in POLA_MODELU:
                if pole not in self.fields and pole in errors.error_dict:
                    for blad in errors.error_dict.pop(pole):
                        if blad.message not in [b.message for b in przeniesione]:
                            przeniesione.append(blad)
            if przeniesione:
                errors.error_dict.setdefault(POLE_FORMULARZA, []).extend(przeniesione)
        super()._update_errors(errors)
