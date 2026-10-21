"""Konfiguracja kolumn ``dynamic_admin_columns`` czytana raz na request.

Zmierzone na kopii produkcji: changelista ``Wydawnictwo_Ciagle`` zadawała
13 zapytań do tabel ``dynamic_columns_*`` na każde (ciepłe) wyświetlenie,
bo ``get_list_display`` jest wołane przez Django kilka razy na request
(``get_changelist_instance``, ``get_sortable_by``,
``get_list_select_related``, eksport), a każde wywołanie od nowa szukało
wiersza ``ModelAdmin`` użytkownika, wiersza globalnego i jego kolumn.
"""

import pytest
from django.contrib import admin as dj_admin
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from dynamic_admin_columns.models import ModelAdmin, ModelAdminColumn
from dynamic_admin_columns.util import qual

from bpp.models import Autor, Wydawnictwo_Ciagle

# Wiersze ModelAdmin (1) + ich kolumny (1) + dwie listy kolumn dla
# okienka wyboru kolumn, renderowane przez ``changelist_view`` pakietu (2).
MAKS_ZAPYTAN_DYNCOL = 4


def _zapytania_dyncol(ctx):
    return sum("dynamic_columns_" in q["sql"] for q in ctx.captured_queries)


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Autor])
def test_changelist_czyta_konfiguracje_kolumn_raz(admin_client, model):
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
    # Rozgrzewka: pierwszy request inicjuje globalny układ kolumn
    # (``ModelAdmin.objects.enable``) — to koszt jednorazowy na proces.
    assert admin_client.get(url).status_code == 200

    with CaptureQueriesContext(connection) as ctx:
        assert admin_client.get(url).status_code == 200

    assert _zapytania_dyncol(ctx) <= MAKS_ZAPYTAN_DYNCOL, [
        q["sql"] for q in ctx.captured_queries if "dynamic_columns_" in q["sql"]
    ]


def _osobisty_uklad(model_admin, user, kolumny):
    """Załóż ``user``-owi osobisty układ: ``kolumny`` = [(nazwa, włączona)]."""
    row = ModelAdmin.objects.create(
        user=user,
        class_name=qual(model_admin.__class__),
        model_ref=ContentType.objects.get_for_model(model_admin.model),
    )
    for ordering, (col_name, enabled) in enumerate(kolumny, start=1):
        ModelAdminColumn.objects.create(
            parent=row, col_name=col_name, enabled=enabled, ordering=ordering
        )
    return row


@pytest.mark.django_db
def test_get_list_display_respektuje_osobisty_uklad(admin_user):
    autor_admin = dj_admin.site._registry[Autor]
    _osobisty_uklad(
        autor_admin,
        admin_user,
        [("email", True), ("tytul", False), ("orcid", True), ("id", True)],
    )
    request = RequestFactory().get("/")
    request.user = admin_user

    oczekiwane = ["nazwisko", "imiona", "email", "orcid", "id"]
    assert list(autor_admin.get_list_display(request)) == oczekiwane

    # Drugie wywołanie w tym samym requeście nie pyta już bazy.
    with CaptureQueriesContext(connection) as ctx:
        assert list(autor_admin.get_list_display(request)) == oczekiwane
        autor_admin.get_list_select_related(request)
        autor_admin.get_sortable_by(request)
    assert _zapytania_dyncol(ctx) == 0


@pytest.mark.django_db
def test_get_list_display_bez_osobistego_ukladu_bierze_globalny(admin_user):
    autor_admin = dj_admin.site._registry[Autor]
    request = RequestFactory().get("/")
    request.user = admin_user

    globalny = ModelAdmin.objects.enable(autor_admin)
    oczekiwane = list(globalny.get_list_display(autor_admin, request))

    assert list(autor_admin.get_list_display(request)) == oczekiwane
    assert "tytul" in oczekiwane


@pytest.mark.django_db
def test_osobny_request_widzi_nowy_uklad(admin_user):
    """Cache żyje tylko w obrębie requestu — zmiana układu widać od razu."""
    autor_admin = dj_admin.site._registry[Autor]
    ModelAdmin.objects.enable(autor_admin)

    r1 = RequestFactory().get("/")
    r1.user = admin_user
    assert "tytul" in autor_admin.get_list_display(r1)

    _osobisty_uklad(autor_admin, admin_user, [("email", True)])

    r2 = RequestFactory().get("/")
    r2.user = admin_user
    assert list(autor_admin.get_list_display(r2)) == [
        "nazwisko",
        "imiona",
        "email",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Autor])
def test_pierwszy_request_w_procesie_nie_odtwarza_ukladu_globalnego(
    admin_client, model
):
    """Aktualny układ globalny nie jest „odtwarzany" kolumna po kolumnie.

    ``ModelAdmin.objects.enable`` robi ``get_or_create`` dla KAŻDEJ kolumny
    (dla ``Wydawnictwo_Ciagle`` ~80 zapytań) przy pierwszym wyświetleniu
    changelisty w każdym procesie workera. Gdy układ w bazie jest już
    zgodny z kodem, wystarczy to sprawdzić jednym zapytaniem.
    """
    model_admin = dj_admin.site._registry[model]
    ModelAdmin.objects.enable(model_admin)
    # Symuluj świeży proces: wyczyść ``cached_property``.
    model_admin.__dict__.pop("_modeladmin_enabled", None)

    url = reverse(
        f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
    )
    with CaptureQueriesContext(connection) as ctx:
        assert admin_client.get(url).status_code == 200

    # + wiersz globalny i nazwy jego kolumn (2)
    assert _zapytania_dyncol(ctx) <= MAKS_ZAPYTAN_DYNCOL + 2, [
        q["sql"] for q in ctx.captured_queries if "dynamic_columns_" in q["sql"]
    ]


@pytest.mark.django_db
def test_nieaktualny_uklad_globalny_jest_uzupelniany(admin_user):
    autor_admin = dj_admin.site._registry[Autor]
    globalny = ModelAdmin.objects.enable(autor_admin)
    globalny.modeladmincolumn_set.filter(col_name="email").delete()
    ModelAdminColumn.objects.create(
        parent=globalny, col_name="nieistniejaca", enabled=True, ordering=999
    )
    autor_admin.__dict__.pop("_modeladmin_enabled", None)

    request = RequestFactory().get("/")
    request.user = admin_user
    kolumny = autor_admin.get_list_display(request)

    assert "email" in kolumny
    assert "nieistniejaca" not in kolumny
