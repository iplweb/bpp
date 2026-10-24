"""Kafelkowy (drag-drop) edytor układu profilu autora dla ``UczelniaAdmin``.

Zastępuje surowy ``<textarea>`` JSON przyjaznym widgetem: JEDNA lista kafelków
sekcji podstrony autora w kolejności renderowania. Każdy kafelek ma uchwyt do
przeciągania (jquery-ui ``.sortable``, dostarczane przez Grappelli), checkbox
widoczności, ``<select>`` szerokości (pół / cała) i opcjonalny ``<select>``
limitu (tylko sekcje ``ma_limit``). Dwie kolejne sekcje „pół” stają na stronie
obok siebie, „cała” zajmuje własny pas.

Na zapis serializuje do schematu JSON, który konsumuje reszta kodu: lista
pozycji ``{"klucz": str, "szerokosc": "pol"|"cala", "widoczna": bool, "limit":
int|None}``. JS re-serializuje kafelki do ukrytego inputa, a ``waliduj_uklad``
w ``clean`` sanityzuje cokolwiek przyjdzie POST-em.

To jest admin (Grappelli) → ikony EMOJI, nie Foundation Icons.
"""

import json

from django import forms
from django.template.loader import get_template

from bpp.profil_autora import (
    DOZWOLONE_LIMITY,
    KATALOG_WG_KLUCZA,
    SZEROKOSC_CALA,
    SZEROKOSC_POL,
    doklej_brakujace,
    waliduj_uklad,
)

#: Opcje selecta szerokości (wartość, etykieta).
OPCJE_SZEROKOSCI = (
    (SZEROKOSC_POL, "½ — obok sąsiada"),
    (SZEROKOSC_CALA, "▭ cała szerokość"),
)


def _parsuj_wartosc(value):
    """Zamień wartość widgetu (JSON-string / lista / puste) na listę pozycji."""
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    return value


def _uporzadkuj_kafelki(value):
    """Zbuduj listę kafelków w kolejności renderowania.

    Każdy kafelek to dict ``{typ, szerokosc, widoczna, limit}``. ``typ`` to
    ``TypSekcji``. Sekcje katalogu nieobecne w ``value`` są doklejane tak samo
    jak na stronie (``doklej_brakujace``), więc nowo dodane sekcje zawsze
    pojawią się w edytorze — w tym miejscu, w którym pojawią się na stronie.
    """
    pozycje = doklej_brakujace(waliduj_uklad(_parsuj_wartosc(value)))
    return [
        {
            "typ": KATALOG_WG_KLUCZA[p["klucz"]],
            "szerokosc": p["szerokosc"],
            "widoczna": p["widoczna"],
            "limit": p["limit"],
        }
        for p in pozycje
    ]


class EdytorUkladuWidget(forms.Widget):
    """Widget renderujący kafelkowy edytor + ukryty input z kanonicznym JSON."""

    template_name = "admin/widgets/uklad_profilu.html"

    class Media:
        css = {"all": ("grappelli/jquery/ui/jquery-ui.min.css",)}
        js = (
            "grappelli/jquery/ui/jquery-ui.min.js",
            "bpp/js/uklad_profilu_edytor.js",
        )

    def render(self, name, value, attrs=None, renderer=None):
        kafelki = _uporzadkuj_kafelki(value)
        # Kanoniczna wartość ukrytego inputa — to, co odczyta JS i ewentualny
        # POST gdy JS nie wystartuje.
        serializowane = json.dumps(
            [
                {
                    "klucz": k["typ"].klucz,
                    "szerokosc": k["szerokosc"],
                    "widoczna": k["widoczna"],
                    "limit": k["limit"],
                }
                for k in kafelki
            ]
        )
        context = {
            "name": name,
            "value_json": serializowane,
            "kafelki": kafelki,
            "opcje_szerokosci": OPCJE_SZEROKOSCI,
            "dozwolone_limity": DOZWOLONE_LIMITY,
        }
        # get_template(...).render(context) — bez request, więc context
        # processors (np. lookup django_site) nie odpalają się.
        return get_template(self.template_name).render(context)

    def value_from_datadict(self, data, files, name):
        """Odczytaj kanoniczny JSON z ukrytego inputa.

        Preferowane: JS zserializował kafelki do ``data[name]``. Gdy JS nie
        wystartował (np. brak JS w teście), wartość ukrytego inputa to nadal
        wyrenderowany JSON z ``render`` — też poprawny. ``clean`` i tak
        przepuści to przez ``waliduj_uklad``.
        """
        return data.get(name)
