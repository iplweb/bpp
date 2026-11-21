"""Dynamiczne klasy formularzy raportów, osiągalne przez import po nazwie.

``form_class_dla`` buduje klasę formularza per ``DefinicjaRaportu`` z
``__module__ = "nowe_raporty.forms_dynamiczne"`` i ``__name__ =
"RaportForm_<slug>"``. django-formdefaults zapisuje ten ``full_name``
w ``FormRepresentation``, a okno „Moje wartości domyślne" odtwarza klasę
przez ``importlib.import_module(...)`` + ``getattr(...)``. Bez tego modułu
import się wywracał (``ModuleNotFoundError``) i okno kończyło się błędem
serwera 500 (FD#528).

Moduł nie trzyma żadnych klas na stałe: ``__getattr__`` (PEP 562) szuka
definicji raportu, której slug daje żądaną nazwę klasy, i buduje klasę na
żądanie — zawsze aktualną względem bieżącej definicji.
"""

from .forms import form_class_dla, nazwa_klasy_formularza


def __getattr__(name):
    if not name.startswith("RaportForm_"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .models import DefinicjaRaportu

    for definicja in DefinicjaRaportu.objects.order_by("pk"):
        if nazwa_klasy_formularza(definicja.slug) == name:
            return form_class_dla(definicja)

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r} "
        "(brak definicji raportu o pasującym slugu)"
    )
