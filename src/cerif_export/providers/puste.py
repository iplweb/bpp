"""Sety zadeklarowane, ale niewypełniane przez BPP.

Wytyczne OpenAIRE for CRIS Managers wymagają, żeby wszystkie dziewięć setów
było zadeklarowane w ``ListSets`` — dosłownie „even if unpopulated". BPP nie
prowadzi ewidencji produktów badawczych, aparatury, projektów ani
finansowania, więc te cztery sety istnieją i odpowiadają pustą listą rekordów
zamiast błędem ``noRecordsMatch`` na poziomie ``ListSets``.

Providery dziedziczą całą logikę z :class:`ProviderPusty` — deklarują
wyłącznie ``set_spec``. ``typ_cerif`` zostaje pusty, bo żaden rekord nigdy
nie powstanie, a wpisanie tu typu sugerowałoby, że kiedyś powstaje.
"""

from cerif_export import const
from cerif_export.providers.base import ProviderPusty


class ProviderProduktow(ProviderPusty):
    """``openaire_cris_products`` — zbiory danych, oprogramowanie."""

    set_spec = const.SET_PRODUCTS


class ProviderProjektow(ProviderPusty):
    """``openaire_cris_projects`` — projekty badawcze."""

    set_spec = const.SET_PROJECTS


class ProviderFinansowania(ProviderPusty):
    """``openaire_cris_funding`` — źródła finansowania."""

    set_spec = const.SET_FUNDING


class ProviderAparatury(ProviderPusty):
    """``openaire_cris_equipments`` — aparatura badawcza."""

    set_spec = const.SET_EQUIPMENTS
