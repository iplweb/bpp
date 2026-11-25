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


@pytest.mark.django_db
def test_fd524_seed_nie_zapisuje_modelu_w_sekcji_inne():
    from flexible_reports.models.report import DATA_FROM_EXCEPT_CATCHALL

    from nowe_raporty.seeding import seed_default_reports

    seed_default_reports()

    inne = ReportElement.objects.filter(data_from=DATA_FROM_EXCEPT_CATCHALL)
    assert inne.exists()
    assert not inne.filter(base_model__isnull=False).exists()


def _dane_formularza_raportu(raport, **zmiany_w_pierwszej_skladowej):
    """Dane POST formularza raportu w adminie — tak, jak wysłałaby je
    przeglądarka (bez pola modelu, którego w formularzu nie ma)."""
    skladowe = list(raport.reportelement_set.order_by("position", "pk"))
    dane = {
        "title": raport.title,
        "slug": raport.slug,
        "template": raport.template,
        "reportelement_set-TOTAL_FORMS": len(skladowe),
        "reportelement_set-INITIAL_FORMS": len(skladowe),
        "reportelement_set-MIN_NUM_FORMS": 0,
        "reportelement_set-MAX_NUM_FORMS": 1000,
        "_save": "Zapisz",
    }
    for nr, skladowa in enumerate(skladowe):
        pola = {
            "id": skladowa.pk,
            "parent": raport.pk,
            "title": skladowa.title,
            "slug": skladowa.slug,
            "data_from": skladowa.data_from,
            "datasource": skladowa.datasource_id or "",
            "table": skladowa.table_id,
            "position": skladowa.position,
        }
        if nr == 0:
            pola.update(zmiany_w_pierwszej_skladowej)
        dane.update({f"reportelement_set-{nr}-{k}": v for k, v in pola.items()})
    return dane


@pytest.mark.django_db
def test_fd524_sekcje_inne_z_zapisanym_modelem_da_sie_przelaczyc_na_zrodlo(
    admin_client,
):
    """Raporty założone przed tą zmianą mają w sekcji „Inne” zapisany model
    (Rekord), a formularz go już nie pokazuje. Przełączenie takiej sekcji na
    „źródło danych” kończyło się błędem 500 przy zapisie raportu
    (django-flexible-reports 0.6.0; poprawione w 0.6.1)."""
    from flexible_reports.models.report import (
        DATA_FROM_DATASOURCE,
        DATA_FROM_EXCEPT_CATCHALL,
    )

    raport = Report.objects.create(title="r", slug="r", template="x")
    inne = ReportElement.objects.create(
        parent=raport,
        title="4.3. Inne",
        slug="tabela_4_3",
        data_from=DATA_FROM_EXCEPT_CATCHALL,
        base_model=_rekord_ct(),
        table=Table.objects.create(label="t"),
    )
    ds = Datasource.objects.create(
        label="ds", base_model=_rekord_ct(), dsl_query="rok = 2020"
    )

    odpowiedz = admin_client.post(
        reverse("admin:flexible_reports_report_change", args=[raport.pk]),
        _dane_formularza_raportu(
            raport, data_from=DATA_FROM_DATASOURCE, datasource=ds.pk
        ),
    )

    assert odpowiedz.status_code == 302
    inne.refresh_from_db()
    assert inne.datasource == ds
    assert inne.base_model is None


@pytest.mark.django_db
def test_fd524_zapis_raportu_nie_rusza_modelu_starej_sekcji_inne(admin_client):
    # Strażnik: zwykła edycja raportu (np. tytułu) nie zmienia sekcji „Inne”
    # zapisanej po staremu, z modelem.
    from flexible_reports.models.report import DATA_FROM_EXCEPT_CATCHALL

    raport = Report.objects.create(title="r", slug="r", template="x")
    inne = ReportElement.objects.create(
        parent=raport,
        title="4.3. Inne",
        slug="tabela_4_3",
        data_from=DATA_FROM_EXCEPT_CATCHALL,
        base_model=_rekord_ct(),
        table=Table.objects.create(label="t"),
    )

    dane = _dane_formularza_raportu(raport)
    dane["title"] = "po zmianie"
    odpowiedz = admin_client.post(
        reverse("admin:flexible_reports_report_change", args=[raport.pk]), dane
    )

    assert odpowiedz.status_code == 302
    inne.refresh_from_db()
    assert inne.base_model == _rekord_ct()
