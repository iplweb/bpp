"""FD#447: „Klonuj” w „Raporty → Tabele” kopiuje tabelę z kolumnami.

Samo klonowanie dostarcza ``django-flexible-reports`` (>= 0.4.0). Testy pilnują
go od strony BPP: na tabeli zakładanej przez seed, przez moduł redagowania,
z polskimi napisami — tak, jak korzysta z niego redaktor.
"""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from flexible_reports.models import Column, ColumnOrder, ReportElement, Table

from nowe_raporty.seeding import definicje, seed_default_reports

POLA_KOLUMNY = [
    "label",
    "position",
    "sortable",
    "attr_name",
    "template",
    "attrs",
    "display_totals",
    "strip_html_on_export",
    "exclude_from_export",
    "footer_template",
]


@pytest.fixture
def tabela(db):
    seed_default_reports()
    return Table.objects.get(label=definicje.TABELA_LABEL)


def _kolumny(tabela):
    return list(
        Column.objects.filter(parent=tabela)
        .order_by("position")
        .values_list(*POLA_KOLUMNY)
    )


def _sortowanie(tabela):
    return list(
        ColumnOrder.objects.filter(table=tabela)
        .order_by("position")
        .values_list("column__label", "position", "desc")
    )


def _klonuj(client, tabela):
    return client.post(
        reverse("admin:flexible_reports_table_clone", args=(tabela.pk,))
    )


def test_fd447_formularz_tabeli_ma_przycisk_klonuj(admin_client, tabela):
    res = admin_client.get(
        reverse("admin:flexible_reports_table_change", args=(tabela.pk,))
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert reverse("admin:flexible_reports_table_clone", args=(tabela.pk,)) in html
    assert "Klonuj" in html


def test_fd447_klon_ma_te_same_kolumny_w_tej_samej_kolejnosci(admin_client, tabela):
    res = _klonuj(admin_client, tabela)

    klon = Table.objects.exclude(pk=tabela.pk).get()
    # po sklonowaniu redaktor ląduje w formularzu KOPII
    assert res.status_code == 302
    assert res.url == reverse("admin:flexible_reports_table_change", args=(klon.pk,))
    assert klon.label == f"{definicje.TABELA_LABEL} (kopia)"
    assert _kolumny(klon) == _kolumny(tabela)
    assert len(_kolumny(klon)) == len(definicje.KOLUMNY)
    for pole in ("base_model", "sort_option", "attrs", "group_prefix"):
        assert getattr(klon, pole) == getattr(tabela, pole), pole
    assert klon.empty_template == tabela.empty_template


def test_fd447_klon_ma_wlasne_sortowanie(admin_client, tabela):
    _klonuj(admin_client, tabela)

    klon = Table.objects.exclude(pk=tabela.pk).get()
    assert _sortowanie(klon) == _sortowanie(tabela) == [
        ("Rok", 0, True),
        ("Opis bibliograficzny", 1, False),
    ]
    # sortowanie kopii wskazuje kolumny KOPII, nie oryginału
    assert set(
        ColumnOrder.objects.filter(table=klon).values_list("column__parent", flat=True)
    ) == {klon.pk}


def test_fd447_kolejny_klon_dostaje_numer(admin_client, tabela):
    _klonuj(admin_client, tabela)
    _klonuj(admin_client, tabela)

    assert set(Table.objects.exclude(pk=tabela.pk).values_list("label", flat=True)) == {
        f"{definicje.TABELA_LABEL} (kopia)",
        f"{definicje.TABELA_LABEL} (kopia 2)",
    }


# --- strażnicy: co ma się NIE zmienić ---------------------------------------


def test_fd447_oryginal_i_raporty_zostaja_nietkniete(admin_client, tabela):
    kolumny_przed = _kolumny(tabela)
    pk_kolumn_przed = set(
        Column.objects.filter(parent=tabela).values_list("pk", flat=True)
    )
    sortowanie_przed = _sortowanie(tabela)
    elementy_przed = ReportElement.objects.filter(table=tabela).count()
    assert elementy_przed

    _klonuj(admin_client, tabela)

    tabela.refresh_from_db()
    assert tabela.label == definicje.TABELA_LABEL
    assert _kolumny(tabela) == kolumny_przed
    assert (
        set(Column.objects.filter(parent=tabela).values_list("pk", flat=True))
        == pk_kolumn_przed
    )
    assert _sortowanie(tabela) == sortowanie_przed
    # raporty dalej korzystają z oryginału; kopii nie używa żaden
    klon = Table.objects.exclude(pk=tabela.pk).get()
    assert ReportElement.objects.filter(table=tabela).count() == elementy_przed
    assert not ReportElement.objects.filter(table=klon).exists()


def test_fd447_zmiana_w_kopii_nie_rusza_oryginalu(admin_client, tabela):
    _klonuj(admin_client, tabela)
    klon = Table.objects.exclude(pk=tabela.pk).get()

    Column.objects.filter(parent=klon, label="Typ MNiSW").update(
        label="Typ pracy"
    )
    Column.objects.filter(parent=klon, label="ID rekordu").delete()

    etykiety = set(Column.objects.filter(parent=tabela).values_list("label", flat=True))
    assert "Typ MNiSW" in etykiety
    assert "ID rekordu" in etykiety
    assert "Typ pracy" not in etykiety


def test_fd447_klonowanie_tylko_przez_post(admin_client, tabela):
    res = admin_client.get(
        reverse("admin:flexible_reports_table_clone", args=(tabela.pk,))
    )
    assert res.status_code == 405
    assert Table.objects.count() == 1


def test_fd447_bez_prawa_dodawania_tabel_nie_da_sie_klonowac(
    client, normal_django_user, tabela
):
    normal_django_user.is_staff = True
    normal_django_user.save()
    normal_django_user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="flexible_reports", codename="view_table"
        )
    )
    client.force_login(normal_django_user)

    res = _klonuj(client, tabela)

    assert res.status_code == 403
    assert Table.objects.count() == 1
