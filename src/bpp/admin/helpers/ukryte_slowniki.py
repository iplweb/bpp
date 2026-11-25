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
from django.db.models import Q

from bpp.models import Jezyk


def _warunek_widocznosci(pole_formularza):
    """Warunek „pozycja jest na liście wyboru” albo ``None``, gdy pole nie
    jest ograniczane."""
    queryset = getattr(pole_formularza, "queryset", None)
    if queryset is None:
        return None
    limit = pole_formularza.get_limit_choices_to()
    if limit:
        return limit if isinstance(limit, Q) else Q(**limit)
    if queryset.model is Jezyk:
        return Q(widoczny=True)
    return None


class ZachowajUkrytaPozycjeSlownikaMixin:
    """Mixin ``ModelForm``: ukryte pozycje słowników znikają z list wyboru,
    ale wartość już zapisana w edytowanym rekordzie zostaje na liście."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nazwa, pole in self.fields.items():
            warunek = _warunek_widocznosci(pole)
            if warunek is None:
                continue
            obecna = getattr(self.instance, f"{nazwa}_id", None)
            if obecna is not None:
                warunek = warunek | Q(pk=obecna)
            pole.queryset = pole.queryset.model._default_manager.filter(warunek)


class FormularzZUkrytymiSlownikami(ZachowajUkrytaPozycjeSlownikaMixin, forms.ModelForm):
    """Do ``form = …`` w inline'ach, które nie mają własnego formularza."""
