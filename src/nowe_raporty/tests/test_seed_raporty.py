import pytest
from django.core.management import call_command
from django.urls import reverse
from flexible_reports.models import Column, Datasource, Report, Table
from model_bakery import baker

from nowe_raporty.models import DefinicjaRaportu

DEFAULT_SLUGS = {
    "raport-autorow",
    "raport-jednostek",
    "raport-wydzialow",
    "raport-uczelni",
}


@pytest.mark.django_db
def test_seed_pusta_baza_tworzy_komplet():
    call_command("seed_raporty")

    assert set(Report.objects.values_list("slug", flat=True)) >= DEFAULT_SLUGS
    # jedna wspolna tabela
    assert Table.objects.count() == 1
    # tabela ma komplet kolumn (7 z dumpu)
    assert Column.objects.filter(parent__label="Publikacje autorów").count() == 7


@pytest.mark.django_db
def test_seed_jest_idempotentny():
    call_command("seed_raporty")
    liczby = (
        Report.objects.count(),
        Table.objects.count(),
        Datasource.objects.count(),
        Column.objects.count(),
    )

    call_command("seed_raporty")

    assert (
        Report.objects.count(),
        Table.objects.count(),
        Datasource.objects.count(),
        Column.objects.count(),
    ) == liczby


@pytest.mark.django_db
def test_seed_nie_nadpisuje_istniejacego_raportu():
    istniejacy = Report.objects.create(
        slug="raport-autorow", title="MOJ TYTUL", template="MOJ SZABLON"
    )

    call_command("seed_raporty")

    istniejacy.refresh_from_db()
    assert istniejacy.title == "MOJ TYTUL"
    assert istniejacy.template == "MOJ SZABLON"
    # pozostale i tak powstaly
    assert set(Report.objects.values_list("slug", flat=True)) >= DEFAULT_SLUGS


@pytest.mark.django_db
def test_seed_nie_nadpisuje_istniejacej_tabeli():
    tabela = baker.make(Table, label="Publikacje autorów")
    baker.make(Column, parent=tabela, label="jedyna")

    call_command("seed_raporty")

    assert Table.objects.filter(label="Publikacje autorów").count() == 1
    # tabela nietknieta - nadal jedna (moja) kolumna
    assert Column.objects.filter(parent=tabela).count() == 1


@pytest.mark.django_db
def test_seed_raport_jednostek_renderuje_sie(
    generuj_raporty_app, jednostka, normal_django_user, grupa_raporty_wyswietlanie
):
    # Po seedzie raport jednostek faktycznie sie renderuje (wszystkie zapytania
    # DSL kompiluja sie wzgledem modelu Rekord, szablon jest poprawny).
    call_command("seed_raporty")

    res = generuj_raporty_app.get(
        reverse(
            "nowe_raporty:raport_generuj",
            args=("raport-jednostek", jednostka.pk, 2020, 2020),
        )
    )
    assert res.status_code == 200
    assert "Publikacje w czasopismach naukowych" in res.text
    assert "Nie znaleziono definicji" not in res.text


@pytest.mark.django_db
def test_seed_raport_uczelni_renderuje_sie(
    generuj_raporty_app, uczelnia, normal_django_user, grupa_raporty_wyswietlanie
):
    # Dorobiony raport-uczelni realnie dziala (sanity calej definicji + DSL 2.x
    # bez obiekt.pk). Domyslnie zaseedowany jako nieaktywny (dawny default
    # POKAZUJ_NIGDY) - aktywujemy go na potrzeby renderu.
    call_command("seed_raporty")

    definicja = DefinicjaRaportu.objects.get(slug="raport-uczelni")
    definicja.aktywny = True
    definicja.poziom_dostepu = DefinicjaRaportu.DOSTEP_ZALOGOWANI
    definicja.save()

    res = generuj_raporty_app.get(
        reverse(
            "nowe_raporty:raport_generuj_uczelnia", args=("raport-uczelni", 2020, 2020)
        )
    )
    assert res.status_code == 200
    assert "Publikacje w czasopismach naukowych" in res.text
