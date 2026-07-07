"""Faza C / issue #438 — model ``Wydzial`` został usunięty (migracja 0467).

„Wydział" to teraz jednostka top-level (``parent IS NULL``); dawny model
nie istnieje ani w rejestrze aplikacji, ani jako tabela.
"""

import pytest
from django.apps import apps
from django.db import connection


def test_model_wydzial_nie_jest_zarejestrowany():
    with pytest.raises(LookupError):
        apps.get_model("bpp", "Wydzial")


@pytest.mark.django_db
def test_tabela_bpp_wydzial_nie_istnieje():
    assert "bpp_wydzial" not in connection.introspection.table_names()
