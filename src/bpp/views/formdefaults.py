"""Widoki okna „Moje wartości domyślne" (django-formdefaults) z obsługą
nieaktualnej klasy formularza.

``FormRepresentation.full_name`` może wskazywać klasę, której już nie ma —
np. raport z ``nowe_raporty`` po zmianie sluga albo usunięciu definicji
(klasa ``nowe_raporty.forms_dynamiczne.RaportForm_<slug>``), albo formularz
przeniesiony w kodzie. Pakiet importuje wtedy klasę bez ochrony i kończy się
błędem 500 (FD#528). Tu sprawdzamy klasę przed wejściem w widok pakietu
i dla nieistniejącej zwracamy 404.
"""

import logging

from django.http import Http404
from formdefaults.util import get_python_class_by_name
from formdefaults.views import SystemFormDefaultsView, UserFormDefaultsView

logger = logging.getLogger(__name__)


class _SprawdzKlaseFormularzaMixin:
    def dispatch(self, request, *args, **kwargs):
        full_name = kwargs.get("form_full_name", "")
        try:
            get_python_class_by_name(full_name)
        except (ImportError, AttributeError, ValueError) as e:
            # ValueError: pusty/niepoprawny moduł w importlib.import_module.
            logger.warning(
                "formdefaults: nie można odtworzyć klasy formularza %r: %s",
                full_name,
                e,
            )
            raise Http404("Ten formularz nie jest już dostępny.") from e
        return super().dispatch(request, *args, **kwargs)


class BppUserFormDefaultsView(_SprawdzKlaseFormularzaMixin, UserFormDefaultsView):
    pass


class BppSystemFormDefaultsView(_SprawdzKlaseFormularzaMixin, SystemFormDefaultsView):
    pass
