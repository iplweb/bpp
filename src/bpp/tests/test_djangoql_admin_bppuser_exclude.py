"""Regresja bezpieczeństwa (#1 z security review): adminowa wyszukiwarka
DjangoQL (``BppQLSchema``) odsłania model użytkownika (``BppUser``, np. przez
reverse-relację ``Autor.user``) wyłącznie z polami z białej listy
(``username``, ``first_name``, ``last_name``) i bez dalszych relacji.

Bez tego ograniczenia pola ``pbn_token`` (żywy token PBN), ``email`` i ``is_superuser``
stają się filtrowalne → blind oracle: zalogowany redaktor eksfiltruje cudzy
(nawet superusera) token PBN znak-po-znaku (``user.pbn_token startswith "…"``).
API i publiczny ``/zapytanie/`` używają schematu z allow-listą i NIE były
podatne — luka dotyczyła wyłącznie pełnego ``BppQLSchema`` (adminy).
"""

import pytest
from django.contrib.auth import get_user_model
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from model_bakery import baker

from bpp.djangoql_schema import POLA_UZYTKOWNIKA_W_SCHEMACIE, BppQLSchema
from bpp.models import Autor


def test_schemat_admina_ogranicza_pola_modelu_uzytkownika():
    """BppUser w BppQLSchema ma wyłącznie pola z białej listy."""
    schema = BppQLSchema(Autor)
    pola = schema.models[schema.model_label(get_user_model())]
    assert set(pola) == set(POLA_UZYTKOWNIKA_W_SCHEMACIE)


def test_relacja_user_autora_prowadzi_do_ograniczonego_modelu():
    """Reverse-relacja ``Autor.user`` istnieje, ale wskazuje na model
    użytkownika z białą listą pól."""
    schema = BppQLSchema(Autor)
    pola_autora = schema.models[schema.model_label(Autor)]
    assert pola_autora["user"].related_model is get_user_model()


@pytest.mark.django_db
def test_filtr_po_user_pbn_token_jest_odrzucony():
    """Filtr po ``user.pbn_token`` musi być odrzucony jako nieznane pole —
    a nie wykonany jako oracle zwracający tak/nie."""
    with pytest.raises(DjangoQLError):
        apply_search(
            Autor.objects.all(),
            'user.pbn_token = "sekret"',
            schema=BppQLSchema,
        )


@pytest.mark.django_db
def test_zwykly_filtr_po_polu_autora_nadal_dziala():
    """Fix nie może zepsuć normalnego filtrowania po polach Autora."""
    baker.make(Autor, nazwisko="Kowalski")
    wynik = apply_search(
        Autor.objects.all(), 'nazwisko = "Kowalski"', schema=BppQLSchema
    )
    assert wynik.count() == 1
