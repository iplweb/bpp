"""Formularze admina a ukryte pozycje słowników (FD#513).

Pozycję słownika (język, typ MNiSW…) można ukryć, żeby nie zaśmiecała list
wyboru. Rekord, który już na nią wskazuje, musi się jednak dalej dać
otworzyć i zapisać: samo ``limit_choices_to`` wycina ukrytą pozycję także
z formularza istniejącego rekordu — pole pokazuje wtedy „---------”,
a zapis kończy się błędem „Wybierz poprawną wartość”.

``ZachowajUkrytaPozycjeSlownikaMixin`` dokłada do listy wyboru wartość,
którą edytowany rekord już ma. Dodatkowo każde pole wskazujące na słownik
języków (także „Język alternatywny”, „Język oryginalny”, język streszczenia
i tytułu, które nie mają ``limit_choices_to``) pokazuje tylko języki
widoczne — plus ten, który rekord już ma.
"""

from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q

from bpp.models import Jezyk


def _jako_q(limit):
    if not limit:
        return None
    return limit if isinstance(limit, Q) else Q(**limit)


def _warunek_widocznosci(formularz, nazwa, pole_formularza):
    """``(warunek, limit_juz_nalozony)`` dla pola wyboru albo ``(None, …)``,
    gdy pole nie jest ograniczane.

    Warunek bierzemy kolejno z: ``limit_choices_to`` pola formularza (pola
    generowane z modelu — Django już je nałożyło na queryset), z pola modelu
    (pola zadeklarowane w formularzu ręcznie, np. „Charakter formalny”
    z pełną listą), a dla słownika języków — „Widoczny”."""
    queryset = getattr(pole_formularza, "queryset", None)
    if queryset is None:
        return None, False
    warunek = _jako_q(pole_formularza.get_limit_choices_to())
    if warunek is not None:
        return warunek, True
    try:
        pole_modelu = formularz._meta.model._meta.get_field(nazwa)
    except FieldDoesNotExist:
        pole_modelu = None
    if pole_modelu is not None and pole_modelu.is_relation:
        if pole_modelu.related_model is not queryset.model:
            return None, False
        warunek = _jako_q(pole_modelu.get_limit_choices_to())
        if warunek is not None:
            return warunek, False
    if queryset.model is Jezyk:
        return Q(widoczny=True), False
    return None, False


class ZachowajUkrytaPozycjeSlownikaMixin:
    """Mixin ``ModelForm``: ukryte pozycje słowników znikają z list wyboru,
    ale wartość już zapisana w edytowanym rekordzie zostaje na liście
    i przechodzi walidację modelu."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: nazwa pola → pk wartości, którą rekord miał przy otwarciu
        #: formularza i która jest dopuszczona mimo ukrycia.
        self._zachowane_wartosci = {}
        for nazwa, pole in self.fields.items():
            warunek, nalozony = _warunek_widocznosci(self, nazwa, pole)
            if warunek is None:
                continue
            obecna = getattr(self.instance, f"{nazwa}_id", None)
            if obecna is not None:
                warunek = warunek | Q(pk=obecna)
                self._zachowane_wartosci[nazwa] = obecna
            # Queryset pola generowanego z modelu jest już zawężony przez
            # ``limit_choices_to`` — budujemy go od nowa; ręcznie
            # zadeklarowany zawężamy, zachowując jego własne filtry.
            baza = (
                pole.queryset.model._default_manager.all()
                if nalozony
                else (pole.queryset)
            )
            pole.queryset = baza.filter(warunek)

    def _get_validation_exclusions(self):
        # ``ForeignKey.validate`` (walidacja MODELU, po walidacji formularza)
        # też sprawdza ``limit_choices_to`` i odrzuciłaby ukrytą wartość,
        # którą rekord już ma. Pomijamy ją tylko dla NIEZMIENIONEJ wartości;
        # wybór innej ukrytej pozycji odrzuca wcześniej pole formularza.
        exclude = super()._get_validation_exclusions()
        for nazwa, pk in self._zachowane_wartosci.items():
            wybrana = self.cleaned_data.get(nazwa)
            if wybrana is not None and wybrana.pk == pk:
                exclude.add(nazwa)
        return exclude


class FormularzZUkrytymiSlownikami(ZachowajUkrytaPozycjeSlownikaMixin, forms.ModelForm):
    """Do ``form = …`` w inline'ach, które nie mają własnego formularza."""
