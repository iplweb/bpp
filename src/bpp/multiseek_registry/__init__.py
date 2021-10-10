from multiseek.logic import Ordering, create_registry

from .fields import *  # noqa
from .reports import multiseek_report_types

from bpp.models import Rekord

registry = create_registry(
    Rekord,
    *multiseek_fields,  # noqa
    ordering=[
        Ordering("", "(nieistotne)"),
        Ordering("tytul_oryginalny", "tytuł oryginalny"),
        Ordering("rok", "rok"),
        Ordering("impact_factor", "impact factor"),
        Ordering("liczba_cytowan", "liczba cytowań"),
        Ordering("liczba_autorow", "liczba autorów"),
        Ordering("punkty_kbn", "punkty PK"),
        Ordering("charakter_formalny__nazwa", "charakter formalny"),
        Ordering("typ_kbn__nazwa", "typ KBN"),
        Ordering("zrodlo_lub_nadrzedne", "źródło/wyd.nadrz."),
        Ordering("utworzono", "utworzono"),
        Ordering("ostatnio_zmieniony", "ostatnio zmieniony"),
    ],
    default_ordering=["-rok", "", ""],
    report_types=multiseek_report_types
)


def _get_fields(self, request):
    """Ta funkcja sortuje pola zgodnie z ustawieniem pola ui_order (czyli bazodanowy
    sort_order obiektu BppMultiseekVisibility) i zwraca je w kolejności.
    """
    return sorted(
        [x for x in self.fields if x.enabled(request)], key=lambda x: x.ui_order
    )


registry.get_fields = lambda request, registry=registry: _get_fields(registry, request)
