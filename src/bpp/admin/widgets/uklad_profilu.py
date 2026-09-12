"""Kafelkowy (drag-drop) edytor układu profilu autora dla ``UczelniaAdmin``.

Zastępuje surowy ``<textarea>`` JSON przyjaznym widgetem: DWIE połączone strefy
(Lewa / Prawa) z kafelkami sekcji podstrony autora. Każdy kafelek ma checkbox
widoczności, opcjonalny ``<select>`` limitu (tylko sekcje ``ma_limit``) i da się
go przeciągnąć MIĘDZY kolumnami (jquery-ui ``.sortable({connectWith})``,
dostarczane przez Grappelli).

Na zapis serializuje do schematu JSON, który konsumuje reszta kodu: lista
pozycji ``{"klucz": str, "kolumna": "lewa"|"prawa", "widoczna": bool, "limit":
int|None}`` (``kolumna`` wynika z tego, w której strefie jest kafelek). JS
re-serializuje kafelki do ukrytego inputa, a ``waliduj_uklad`` w ``clean``
sanityzuje cokolwiek przyjdzie POST-em.

To jest admin (Grappelli) → ikony EMOJI, nie Foundation Icons.
"""

import json

from django import forms
from django.template.loader import get_template

from bpp.profil_autora import (
    DOZWOLONE_LIMITY,
    KATALOG_SEKCJI,
    KATALOG_WG_KLUCZA,
    KOLUMNA_LEWA,
    KOLUMNA_PRAWA,
    domyslny_uklad,
    waliduj_uklad,
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
    """Zbuduj kafelki rozdzielone na kolumny: ``{"lewa": [...], "prawa": [...]}``.

    Każdy kafelek to dict ``{typ, kolumna, widoczna, limit}``. ``typ`` to
    ``TypSekcji``. Kolejność: najpierw zapisane pozycje (w ich zapisanej
    kolumnie), potem sekcje katalogu nieobecne w ``value`` — doklejane z
    domyślnymi ustawieniami w ich DOMYŚLNEJ kolumnie (forward-compat, jak
    ``rozwiaz_uklad``), więc nowo dodane sekcje zawsze pojawią się w edytorze.
    """
    zapisany = waliduj_uklad(_parsuj_wartosc(value))
    wg_klucza = {p["klucz"]: p for p in zapisany}
    domyslne = {p["klucz"]: p for p in domyslny_uklad()}

    kolejnosc = [p["klucz"] for p in zapisany]
    for typ in KATALOG_SEKCJI:
        if typ.klucz not in wg_klucza:
            kolejnosc.append(typ.klucz)

    kafelki = {KOLUMNA_LEWA: [], KOLUMNA_PRAWA: []}
    for klucz in kolejnosc:
        pozycja = wg_klucza.get(klucz) or domyslne[klucz]
        kolumna = pozycja["kolumna"]
        kafelki[kolumna].append(
            {
                "typ": KATALOG_WG_KLUCZA[klucz],
                "kolumna": kolumna,
                "widoczna": pozycja["widoczna"],
                "limit": pozycja["limit"],
            }
        )
    return kafelki


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
        # POST gdy JS nie wystartuje. Kolejność: lewa, potem prawa (JS i tak
        # serializuje per-strefa, więc kolejność tu jest tylko fallbackiem).
        serializowane = json.dumps(
            [
                {
                    "klucz": k["typ"].klucz,
                    "kolumna": k["kolumna"],
                    "widoczna": k["widoczna"],
                    "limit": k["limit"],
                }
                for k in kafelki[KOLUMNA_LEWA] + kafelki[KOLUMNA_PRAWA]
            ]
        )
        context = {
            "name": name,
            "value_json": serializowane,
            "kafelki_lewa": kafelki[KOLUMNA_LEWA],
            "kafelki_prawa": kafelki[KOLUMNA_PRAWA],
            "kolumna_lewa": KOLUMNA_LEWA,
            "kolumna_prawa": KOLUMNA_PRAWA,
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
