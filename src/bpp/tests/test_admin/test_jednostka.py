from unittest.mock import patch

from django.contrib import admin
from django.db import ProgrammingError
from django.urls import reverse

from bpp.admin.core import BaseBppAdminMixin
from bpp.admin.jednostka import JednostkaAdmin
from bpp.models import Jednostka, Uczelnia


def test_admin_struktura_JednostkaAdmin_uczelnia_jednostki_alfabetycznie(
    uczelnia: Uczelnia, admin_client
):
    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    assert (
        admin_client.get(reverse("admin:bpp_jednostka_changelist")).status_code == 200
    )


def test_JednostkaAdmin_list_per_page_toleruje_niezmigrowana_kolumne(db):
    # Regresja (multi-hosted upgrade): `migrate` uruchamia system checks
    # PRZED zastosowaniem migracji. Check admina odczytuje `list_per_page`,
    # które odpytuje bazę. Na ISTNIEJĄCEJ instalacji w trakcie upgrade'u
    # tabela `bpp_uczelnia` już istnieje, ale świeżo dodana, jeszcze
    # nie-zmigrowana kolumna `site_id` — nie. Zapytanie rzuca wtedy
    # ProgrammingError (UndefinedColumn). Guard MUSI to złapać i zdegradować
    # do wartości domyślnej — inaczej `migrate` pada i nie da się zastosować
    # migracji, która by tę kolumnę dodała (deadlock upgrade'u).
    ma = JednostkaAdmin(Jednostka, admin.site)
    with patch.object(
        Uczelnia.objects,
        "get_for_request",
        side_effect=ProgrammingError("kolumna bpp_uczelnia.site_id nie istnieje"),
    ):
        assert ma.get_list_per_page() == BaseBppAdminMixin.list_per_page


def test_admin_struktura_JednostkaAdmin_uczelnia_jednostki_wg_kolejnosci(
    uczelnia: Uczelnia, admin_client
):
    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()

    assert (
        admin_client.get(reverse("admin:bpp_jednostka_changelist")).status_code == 200
    )
