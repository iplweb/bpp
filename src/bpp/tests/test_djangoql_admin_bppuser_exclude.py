"""Regresja bezpieczeństwa (#1 z security review): adminowa wyszukiwarka
DjangoQL (``BppQLSchema``) nie może odsłaniać modelu użytkownika (``BppUser``)
przez reverse-relację ``Autor.user``.

Bez wykluczenia pola ``pbn_token`` (żywy token PBN), ``email`` i ``is_superuser``
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

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Autor


def test_schemat_admina_wyklucza_model_uzytkownika():
    """BppUser jest wykluczony z BppQLSchema niezależnie od modelu bazowego."""
    assert BppQLSchema(Autor).excluded(get_user_model()) is True


def test_relacja_user_autora_nie_istnieje_w_schemacie():
    """Reverse-relacja ``Autor.user`` jest wycięta → 'user' to nieznane pole."""
    schema = BppQLSchema(Autor)
    pola_autora = schema.models[schema.model_label(Autor)]
    assert "user" not in pola_autora


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
