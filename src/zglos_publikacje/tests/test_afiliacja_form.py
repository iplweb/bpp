"""#438: formularz zgłoszenia publikacji nie pozwala zgłaszającemu wybrać dla
autora jednostki nieprzyjmującej afiliacji (np. węzła rodzaju „Wydział").

Formularz ``Zgloszenie_Publikacji_AutorForm`` nie ma pola ``afiliuje`` — każdy
zgłoszony autor dostaje ``afiliuje=True``. Bez tej walidacji wybór wydziału
kończył się nieczytelnym błędem walidacji modelu (o polu 'Afiliuje', którego w
formularzu nie ma) dopiero przy zapisie.
"""

import pytest

from bpp.models import RodzajJednostki
from zglos_publikacje.forms import Zgloszenie_Publikacji_AutorForm


def _form_data(autor, jednostka, rok=2024):
    return {
        "autor": autor.pk,
        "jednostka": jednostka.pk,
        "dyscyplina_naukowa": "",
        "rok": rok,
    }


@pytest.mark.django_db
def test_form_odrzuca_jednostke_rodzaju_wydzial(autor, jednostka):
    jednostka.rodzaj = RodzajJednostki.objects.get(nazwa="Wydział")
    jednostka.save()

    form = Zgloszenie_Publikacji_AutorForm(data=_form_data(autor, jednostka))

    assert not form.is_valid()
    assert "jednostka" in form.errors


@pytest.mark.django_db
def test_form_odrzuca_jednostke_obca(autor, jednostka):
    jednostka.skupia_pracownikow = False
    jednostka.save()

    form = Zgloszenie_Publikacji_AutorForm(data=_form_data(autor, jednostka))

    assert not form.is_valid()
    assert "jednostka" in form.errors


@pytest.mark.django_db
def test_form_przyjmuje_zwykla_jednostke(autor, jednostka):
    # Zwykła jednostka (przyjmuje afiliację) — brak błędu na polu ``jednostka``.
    # (Formularz może być niepełny z innych powodów — np. brak rekordu
    # nadrzędnego — ale nie z powodu jednostki.)
    form = Zgloszenie_Publikacji_AutorForm(data=_form_data(autor, jednostka))
    form.is_valid()

    assert "jednostka" not in form.errors
