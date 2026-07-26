"""Widoki raportu kompletności danych POL-on.

Pakiet re-eksportuje publiczne nazwy, żeby ``urls.py`` i testy mogły pisać
``from kompletnosc_polon import views`` bez wiedzy o podziale na moduły —
tak samo jak w :mod:`ewaluacja_metryki.views`.
"""

from .lista import (
    ListaKompletnosciView,
    ma_jakikolwiek_brak,
    sa_przypiete_dyscypliny,
    zbierz_nierozpoznane,
    zbierz_po_autorach,
)
from .mixins import (
    PelneUprawnieniaEwaluacjiMixin,
    RaportKompletnosciMixin,
    url_formularza_admina,
)
from .szczegoly import (
    SzczegolyKompletnosciView,
    zbierz_nierozpoznane_autora,
    zbierz_pozycje,
)

__all__ = [
    # Mixiny i pomocnicy
    "PelneUprawnieniaEwaluacjiMixin",
    "RaportKompletnosciMixin",
    "url_formularza_admina",
    "ma_jakikolwiek_brak",
    "sa_przypiete_dyscypliny",
    # Widok zbiorczy
    "ListaKompletnosciView",
    "zbierz_po_autorach",
    "zbierz_nierozpoznane",
    # Widok szczegółów
    "SzczegolyKompletnosciView",
    "zbierz_pozycje",
    "zbierz_nierozpoznane_autora",
]
