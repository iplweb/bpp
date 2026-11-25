from django.db.models import Case, Q, TextField, When
from multiseek.logic import Ordering, UnknownField, create_registry

from bpp.models import Rekord

from .dawne_etykiety import aktualna_etykieta
from .fields import *  # noqa
from .reports import multiseek_report_types

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
        Ordering("punkty_kbn", "punkty MNiSW"),
        Ordering("charakter_formalny__nazwa", "charakter formalny"),
        Ordering("typ_kbn__nazwa", "typ MNiSW"),
        Ordering("zrodlo_lub_nadrzedne", "źródło/wyd.nadrz."),
        Ordering("utworzono", "utworzono"),
        Ordering("ostatnio_zmieniony", "ostatnio zmieniony"),
    ],
    default_ordering=["-rok", ""],
    report_types=multiseek_report_types,
)


def _get_default_queryset_for_model():
    return Rekord.objects.all().annotate(
        zrodlo_lub_nadrzedne=Case(
            When(
                Q(zrodlo_id=None),
                then="wydawnictwo_nadrzedne__tytul_oryginalny",
            ),
            When(
                Q(wydawnictwo_nadrzedne_id=None),
                then="zrodlo__nazwa",
            ),
            output_field=TextField(),
        )
    )


registry.get_default_queryset_for_model = _get_default_queryset_for_model

# Sortowanie najwyżej na 2 poziomach (multiseek domyślnie daje 3). Formularze
# zapisane wcześniej z trzecim kryterium działają — trzecie jest pomijane.
registry.order_boxes = ["Sortuj według", "następnie"]


def _get_fields(self, request):
    """Ta funkcja sortuje pola zgodnie z ustawieniem pola ui_order (czyli bazodanowy
    sort_order obiektu BppMultiseekVisibility) i zwraca je w kolejności.
    """
    return sorted(
        (x for x in self.fields if x.enabled(request)), key=lambda x: x.ui_order
    )


registry.get_fields = lambda request, registry=registry: _get_fields(registry, request)


def _get_field_by_name(nazwa, registry=registry):
    """Pole po etykiecie — także DAWNEJ (patrz ``dawne_etykiety.py``).

    Nieznana etykieta to ``UnknownField`` (bazowa metoda zwraca ``None``,
    przez co odtwarzanie formularza kończyło się ``AttributeError``); widoki
    wyszukiwarki łapią ten wyjątek i czyszczą formularz zamiast zwracać 500.
    """
    szukana = aktualna_etykieta(nazwa)
    for pole in registry.fields:
        if str(pole.label) == szukana:
            return pole
    raise UnknownField(f"Nieznane pole wyszukiwarki: {nazwa!r}")


registry.get_field_by_name = _get_field_by_name
