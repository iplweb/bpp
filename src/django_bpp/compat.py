"""Łatki zgodnościowe dla nieutrzymywanych zależności third-party.

Importowany z ``django_bpp.settings.base`` — a więc ZANIM
``django.setup()`` wywoła ``apps.populate()`` i zacznie importować
moduły z ``INSTALLED_APPS``. To jedyne okno, w którym da się wstawić
brakujący moduł do ``sys.modules`` tak, żeby zdążył przed importem
pakietu, który go szuka.

Każda łatka tutaj to dług techniczny z jawnym warunkiem wyjścia.
Nie dokładaj kolejnych bez opisania, co ma się wydarzyć, żeby
można ją było skasować.
"""

import sys
import types


def _zalataj_itercompat():
    """Przywróć ``django.utils.itercompat`` dla ``django-admin-tools``.

    ``django-admin-tools`` 0.9.3 (ostatnie wydanie, klasyfikatory kończą
    się na Django 4.0) ma w ``admin_tools/dashboard/modules.py``::

        from django.utils.itercompat import is_iterable

    Django 6.1 usunęło ten moduł, więc import wywala się na starcie i
    kładzie całe ``apps.populate()``.

    Import jest **martwy** — ``is_iterable`` nie jest używane nigdzie w
    ``admin_tools`` (sprawdzone grepem po całym pakiecie). Wystarczy więc
    dostarczyć nazwę; żaden kod jej nie zawoła. Implementacja i tak jest
    wierna oryginałowi z Django (``iter()`` + ``TypeError``), żeby łatka
    nie kłamała, gdyby kiedyś jednak została użyta.

    WARUNEK WYJŚCIA: skasować razem z całym ``django-admin-tools``, gdy
    BPP przejdzie na inny mechanizm dashboardu/menu, albo gdy powstanie
    fork ``django-admin-tools-iplweb`` z usuniętą tą linią. Sam upstream
    jest praktycznie martwy (0.9.3 to ostatnie wydanie), więc czekanie na
    poprawkę od niego nie jest realnym planem.
    """
    if "django.utils.itercompat" in sys.modules:
        return

    modul = types.ModuleType("django.utils.itercompat")
    modul.__doc__ = "Shim BPP dla django-admin-tools — patrz django_bpp.compat."

    def is_iterable(x):
        try:
            iter(x)
        except TypeError:
            return False
        return True

    modul.is_iterable = is_iterable
    sys.modules["django.utils.itercompat"] = modul


def zalataj_zaleznosci():
    """Nałóż wszystkie łatki zgodnościowe. Idempotentne."""
    _zalataj_itercompat()
