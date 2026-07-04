"""Rejestr poziomów raportu — jedyna część "raportu", która zostaje KODEM.

Każdy poziom (uczelnia/wydział/jednostka/autor) mapuje na: model obiektu, czy
URL niesie ``pk``, funkcję bazowego querysetu ``Rekord`` (logika ORM, której nie
da się wyrazić jako dana — patrz slice A), oraz pole wyboru obiektu do
formularza. Reszta definicji raportu (nazwa, slug, template, uprawnienia) jest
danymi w ``DefinicjaRaportu``.
"""

from dal import autocomplete
from django import forms

from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni

from .models import DefinicjaRaportu


def _base_autor(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        return Rekord.objects.prace_autora_z_afiliowanych_jednostek(obiekt)
    return Rekord.objects.prace_autora(obiekt)


def _base_jednostka(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        return Rekord.objects.prace_jednostki(obiekt, afiliowane=True)
    return Rekord.objects.prace_jednostki(obiekt)


def _base_wydzial(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        return Rekord.objects.prace_wydzialu(obiekt, afiliowane=True)
    return Rekord.objects.prace_wydzialu(obiekt)


def _base_uczelnia(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        qs = Rekord.objects.filter(autorzy__afiliuje=True)
    else:
        qs = Rekord.objects.all()
    return scope_rekord_do_uczelni(qs, obiekt)


def _pole(label, model, url):
    return forms.ModelChoiceField(
        label=label,
        queryset=model.objects.all(),
        widget=autocomplete.ModelSelect2(url=url),
    )


class PoziomConfig:
    def __init__(self, model, ma_pk, base_queryset, pole_factory):
        self.model = model
        self.ma_pk = ma_pk
        self.base_queryset = base_queryset
        self.pole_factory = pole_factory  # () -> forms.Field | None

    def pole_obiektu(self):
        return self.pole_factory()


POZIOMY = {
    DefinicjaRaportu.POZIOM_AUTOR: PoziomConfig(
        Autor,
        True,
        _base_autor,
        lambda: _pole("Autor", Autor, "bpp:public-autor-autocomplete"),
    ),
    DefinicjaRaportu.POZIOM_JEDNOSTKA: PoziomConfig(
        Jednostka,
        True,
        _base_jednostka,
        lambda: _pole("Jednostka", Jednostka, "bpp:public-jednostka-autocomplete"),
    ),
    # Faza B (#438): „wydział" = jednostka-korzeń (parent IS NULL). Picker i
    # obiekt raportu to teraz Jednostka top-level, nie Wydzial.
    DefinicjaRaportu.POZIOM_WYDZIAL: PoziomConfig(
        Jednostka,
        True,
        _base_wydzial,
        lambda: _pole(
            "Wydział", Jednostka, "bpp:public-jednostka-toplevel-autocomplete"
        ),
    ),
    DefinicjaRaportu.POZIOM_UCZELNIA: PoziomConfig(
        Uczelnia,
        False,
        _base_uczelnia,
        lambda: None,
    ),
}
