"""FD#524: „Podstawowy model” wybiera się raz — w źródle danych.

Formularze tabeli i składowej raportu nie pytają już o model; tabela bierze go
ze źródeł danych, z którymi jest używana (``django-flexible-reports`` >= 0.6.0).
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.urls import reverse
from flexible_reports.models import Column, Datasource, Report, ReportElement, Table

from bpp.models.cache import Rekord

pytest.importorskip(
    "flexible_reports.base_models",
    reason="wymaga django-flexible-reports >= 0.6.0 (model tabeli ze źródła danych)",
)


def _rekord_ct():
    return ContentType.objects.get_for_model(Rekord)


@pytest.mark.django_db
def test_fd524_formularz_tabeli_nie_pyta_o_model(admin_client):
    odpowiedz = admin_client.get(reverse("admin:flexible_reports_table_add"))
    assert "base_model" not in odpowiedz.context["adminform"].form.fields
    assert "Podstawowy model" not in odpowiedz.rendered_content


@pytest.mark.django_db
def test_fd524_formularz_raportu_nie_pyta_o_model(admin_client):
    odpowiedz = admin_client.get(reverse("admin:flexible_reports_report_add"))
    (skladowe,) = odpowiedz.context["inline_admin_formsets"]
    assert "base_model" not in skladowe.formset.form.base_fields
    assert "datasource" in skladowe.formset.form.base_fields
    assert "Podstawowy model" not in odpowiedz.rendered_content


@pytest.mark.django_db
def test_fd524_nowa_tabela_bez_modelu_waliduje_kolumny_na_rekordzie():
    # Tabela jeszcze nigdzie nieużyta: model domyślny z ustawień (Rekord).
    tabela = Table.objects.create(label="nowa")
    assert tabela.base_model is None
    assert tabela.get_base_models() == [Rekord]

    Column(parent=tabela, label="Rok", attr_name="rok").clean()
    with pytest.raises(ValidationError):
        Column(parent=tabela, label="Zły", attr_name="nie_ma_takiego_pola").clean()


@pytest.mark.django_db
def test_fd524_tabela_bierze_model_ze_zrodla_danych():
    from bpp.models import Autor

    autor_ct = ContentType.objects.get_for_model(Autor)
    # Tabela zapisana po staremu, z własnym modelem (Rekord)…
    tabela = Table.objects.create(label="t", base_model=_rekord_ct())
    ds = Datasource.objects.create(
        label="autorzy", base_model=autor_ct, dsl_query='nazwisko = "x"'
    )
    raport = Report.objects.create(title="r", slug="r")
    ReportElement.objects.create(
        parent=raport, title="s", slug="s", datasource=ds, table=tabela
    )

    # …ale użyta ze źródłem danych o innym modelu: decyduje źródło danych.
    assert tabela.get_base_models() == [Autor]
    Column(parent=tabela, label="Nazwisko", attr_name="nazwisko").clean()
    with pytest.raises(ValidationError):
        Column(parent=tabela, label="Rok", attr_name="rok").clean()


@pytest.mark.django_db
def test_fd524_domyslne_raporty_nadal_sie_zakladaja_i_waliduja():
    """Strażnik: seed domyślnych raportów (tabela „Publikacje autorów”, sekcja
    „Inne” bez źródła danych) działa jak dotąd, a kolumny tabeli przechodzą
    walidację na modelu wziętym ze źródeł danych."""
    from nowe_raporty.seeding import definicje as d
    from nowe_raporty.seeding import seed_default_reports

    seed_default_reports()

    tabela = Table.objects.get(label=d.TABELA_LABEL)
    assert tabela.get_base_models() == [Rekord]
    for kolumna in Column.objects.filter(parent=tabela):
        kolumna.clean()

    for element in ReportElement.objects.all():
        element.clean()
