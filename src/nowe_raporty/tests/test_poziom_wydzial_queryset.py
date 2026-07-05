"""F4 (#438): pole wyboru poziomu „wydział" waliduje TYLKO widoczne korzenie.

``forms.ModelChoiceField.queryset`` decyduje, jakie pk przejdą walidację —
widget Select2 ogranicza tylko UI. Bez zawężenia querysetu do widocznych
korzeni (``parent IS NULL``) stary bookmark ``?...=<Wydzial.pk>`` mógłby trafić
w pk niepowiązanej jednostki i wygenerować cichy zły raport.
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.poziomy import POZIOMY


@pytest.mark.django_db
def test_poziom_wydzial_queryset_tylko_widoczne_korzenie():
    u = baker.make(Uczelnia)
    korzen = baker.make(Jednostka, uczelnia=u, parent=None, widoczna=True)
    dziecko = baker.make(Jednostka, uczelnia=u, parent=korzen, widoczna=True)
    ukryty_korzen = baker.make(Jednostka, uczelnia=u, parent=None, widoczna=False)

    field = POZIOMY[DefinicjaRaportu.POZIOM_WYDZIAL].pole_obiektu()
    pks = set(field.queryset.values_list("pk", flat=True))

    assert korzen.pk in pks  # widoczny korzeń — dozwolony
    assert dziecko.pk not in pks  # nie-korzeń — odrzucony przez walidację
    assert ukryty_korzen.pk not in pks  # ukryty korzeń — odrzucony


@pytest.mark.django_db
def test_poziom_wydzial_obiekt_queryset_tylko_widoczne_korzenie():
    """#438 (finding 5): ``obiekt_queryset`` (get_object na URL-u generowania,
    POZA walidacją formularza) też zawęża do widocznych korzeni — inaczej
    bookmark ``?pk=<dowolna jednostka>`` generował cichy zły raport / wyciek
    ukrytej jednostki."""
    u = baker.make(Uczelnia)
    korzen = baker.make(Jednostka, uczelnia=u, parent=None, widoczna=True)
    dziecko = baker.make(Jednostka, uczelnia=u, parent=korzen, widoczna=True)
    ukryty_korzen = baker.make(Jednostka, uczelnia=u, parent=None, widoczna=False)

    qs = POZIOMY[DefinicjaRaportu.POZIOM_WYDZIAL].obiekt_queryset()
    pks = set(qs.values_list("pk", flat=True))

    assert korzen.pk in pks
    assert dziecko.pk not in pks  # nie-korzeń → get_object da 404
    assert ukryty_korzen.pk not in pks
