"""Sety zadeklarowane, ale niewypełniane przez BPP.

Wytyczne OpenAIRE for CRIS Managers wymagają, żeby wszystkie dziewięć setów
było zadeklarowane w ``ListSets`` — dosłownie „even if unpopulated". BPP nie
prowadzi ewidencji produktów badawczych ani aparatury, więc te dwa sety
istnieją i odpowiadają pustą listą rekordów zamiast błędem
``noRecordsMatch`` na poziomie ``ListSets``.

Projekty i finansowanie były tu do czasu wprowadzenia modeli ``Projekt``
i ``Finansowanie`` — mają dziś własne providery
(``providers/projekty.py``, ``providers/finansowanie.py``).

Providery dziedziczą całą logikę z :class:`ProviderPusty` — deklarują
wyłącznie ``set_spec``. ``typ_cerif`` zostaje pusty, bo żaden rekord nigdy
nie powstanie, a wpisanie tu typu sugerowałoby, że kiedyś powstaje.
"""

from cerif_export import const
from cerif_export.providers.base import ProviderPusty


class ProviderProduktow(ProviderPusty):
    """``openaire_cris_products`` — zbiory danych, oprogramowanie."""

    set_spec = const.SET_PRODUCTS


class ProviderAparatury(ProviderPusty):
    """``openaire_cris_equipments`` — aparatura badawcza."""

    set_spec = const.SET_EQUIPMENTS
