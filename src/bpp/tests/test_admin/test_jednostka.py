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


def test_JednostkaAdmin_list_filter_parent_zawęża_do_dzieci(
    admin_client, jednostka: Jednostka, jednostka_podrzedna: Jednostka, druga_jednostka
):
    # Regresja/domknięcie III-3: `JednostkaNadrzednaFilter` (#438 Faza B,
    # III-3a, własny DAL-owy autocomplete zamiast
    # `admin_auto_filters.AutocompleteFilterFactory`) musi realnie zawężać
    # queryset changelisty po `parent`, nie tylko renderować widget.
    response = admin_client.get(
        reverse("admin:bpp_jednostka_changelist"), {"parent": jednostka.pk}
    )
    assert response.status_code == 200

    result_list = list(response.context["cl"].result_list)
    assert jednostka_podrzedna in result_list
    assert jednostka not in result_list
    assert druga_jednostka not in result_list


def test_JednostkaNadrzednaFilter_widget_i_media_w_changeliście(admin_client):
    # Smoke test Media/widgetu (#438 Faza B, III-3a): changelist NIE wciąga
    # automatycznie mediów widgetów pól z `list_filter` (w odróżnieniu od
    # formularza zmiany) — bez własnej `Media` na filtrze Select2/DAL nie
    # zainicjalizowałby się w ogóle. Sprawdzamy, że statyki Select2/DAL oraz
    # sam widget (`data-autocomplete-light-url` na pole `parent`) trafiają
    # do wyrenderowanej strony changelisty.
    response = admin_client.get(reverse("admin:bpp_jednostka_changelist"))
    assert response.status_code == 200

    content = response.content.decode()
    # Substringi bez rozszerzenia - ManifestStaticFilesStorage w testach
    # hashuje nazwy plików (np. `select2.min.61e40dc7cb03.js`), więc dokładna
    # nazwa pliku `select2.js` by tu nie wystąpiła.
    assert "autocomplete_light/select2" in content
    assert "admin/js/vendor/select2/select2.full" in content
    assert 'id="id_parent"' in content
    assert "data-autocomplete-light-url" in content
