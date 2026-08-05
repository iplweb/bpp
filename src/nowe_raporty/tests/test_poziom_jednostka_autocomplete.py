"""Regresja #438: POZIOM_JEDNOSTKA musi używać ungated public autocomplete.

Raporty mogą być dostępne anonimowo (``DefinicjaRaportu.DOSTEP_WSZYSCY``),
więc pole wyboru Jednostki w formularzu raportu nie może wskazywać na
``bpp:jednostka-autocomplete`` -- ten endpoint jest ``LoginRequiredMixin``
i anonimowy użytkownik dostałby martwy Select2 (AJAX 302 -> login).
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Jednostka
from nowe_raporty.forms import form_class_dla
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.poziomy import POZIOMY


def test_poziom_jednostka_uzywa_ungated_public_autocomplete():
    field = POZIOMY[DefinicjaRaportu.POZIOM_JEDNOSTKA].pole_obiektu()

    assert field.widget.url == reverse("bpp:public-jednostka-autocomplete")
    assert field.widget.url != reverse("bpp:jednostka-autocomplete")


def _form_jednostka(rf, uczelnia):
    definicja = baker.make(
        DefinicjaRaportu,
        slug="r-jednostka-picker",
        poziom=DefinicjaRaportu.POZIOM_JEDNOSTKA,
    )
    request = rf.get("/")
    request._uczelnia = uczelnia
    return form_class_dla(definicja)(request=request)


@pytest.mark.django_db
def test_poziom_jednostka_wyklucza_korzenie_gdy_uczelnia_uzywa_wydzialow(rf, uczelnia):
    """#438: gdy uczelnia UŻYWA wydziałów, pole „Jednostka" nie oferuje
    korzeni (to „wydziały", mają własny raport poziomu „wydział"), a picker
    celuje w wariant „nie-toplevel" — analogicznie do rankingu autorów."""
    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()

    korzen = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, widoczna=True, aktualna=True
    )
    dziecko = baker.make(
        Jednostka, uczelnia=uczelnia, parent=korzen, widoczna=True, aktualna=True
    )

    form = _form_jednostka(rf, uczelnia)
    qs = form.fields["obiekt"].queryset

    assert korzen not in qs, "korzeń (wydział) nie powinien być na liście jednostek"
    assert dziecko in qs, "jednostka podrzędna powinna być wybieralna"
    assert form.fields["obiekt"].widget.url == reverse(
        "bpp:public-jednostka-nietoplevel-autocomplete"
    )


@pytest.mark.django_db
def test_poziom_jednostka_zawiera_korzenie_gdy_uczelnia_bez_wydzialow(rf, uczelnia):
    """Bez wydziałów jednostki-korzenie SĄ zwykłymi jednostkami — muszą być
    wybieralne, a picker to domyślny public autocomplete."""
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()

    korzen = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, widoczna=True, aktualna=True
    )

    form = _form_jednostka(rf, uczelnia)
    qs = form.fields["obiekt"].queryset

    assert korzen in qs
    assert form.fields["obiekt"].widget.url == reverse(
        "bpp:public-jednostka-autocomplete"
    )


@pytest.mark.django_db
def test_poziom_jednostka_bez_requestu_nie_zaweza(uczelnia):
    """Ścieżki bez requestu (post_migrate, introspekcja formdefaults) muszą
    dalej działać — bez uczelni nie zawężamy (None-tolerant)."""
    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()

    korzen = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, widoczna=True, aktualna=True
    )

    definicja = baker.make(
        DefinicjaRaportu,
        slug="r-jednostka-picker-noreq",
        poziom=DefinicjaRaportu.POZIOM_JEDNOSTKA,
    )
    form = form_class_dla(definicja)()

    assert korzen in form.fields["obiekt"].queryset
