"""Regresja #438: POZIOM_JEDNOSTKA musi używać ungated public autocomplete.

Raporty mogą być dostępne anonimowo (``DefinicjaRaportu.DOSTEP_WSZYSCY``),
więc pole wyboru Jednostki w formularzu raportu nie może wskazywać na
``bpp:jednostka-autocomplete`` -- ten endpoint jest ``LoginRequiredMixin``
i anonimowy użytkownik dostałby martwy Select2 (AJAX 302 -> login).
"""

from django.urls import reverse

from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.poziomy import POZIOMY


def test_poziom_jednostka_uzywa_ungated_public_autocomplete():
    field = POZIOMY[DefinicjaRaportu.POZIOM_JEDNOSTKA].pole_obiektu()

    assert field.widget.url == reverse("bpp:public-jednostka-autocomplete")
    assert field.widget.url != reverse("bpp:jednostka-autocomplete")
