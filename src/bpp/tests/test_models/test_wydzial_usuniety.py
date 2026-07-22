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


@pytest.mark.parametrize("marker", ["legacy_wydzial_id", "jest_lustrem"])
def test_markery_konwersji_usuniete_z_modelu(marker):
    # Faza C (#438): markery tożsamości konwersji (0468) — potrzebne tylko
    # w trakcie Fazy B — znikają po dropie modelu Wydzial.
    from django.core.exceptions import FieldDoesNotExist

    from bpp.models import Jednostka

    with pytest.raises(FieldDoesNotExist):
        Jednostka._meta.get_field(marker)


@pytest.mark.django_db
@pytest.mark.parametrize("kolumna", ["legacy_wydzial_id", "jest_lustrem"])
def test_kolumny_markerow_usuniete_z_tabeli(kolumna):
    with connection.cursor() as cursor:
        kolumny = {
            col.name
            for col in connection.introspection.get_table_description(
                cursor, "bpp_jednostka"
            )
        }
    assert kolumna not in kolumny
