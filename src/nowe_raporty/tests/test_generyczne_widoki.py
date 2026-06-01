import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models.autor import Autor
from nowe_raporty.forms import form_class_dla
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.seeding import seed_default_reports


@pytest.mark.django_db
def test_dynamiczne_klasy_formularzy_unikalne_per_definicja():
    d1 = baker.make(
        DefinicjaRaportu, slug="raport-a", poziom=DefinicjaRaportu.POZIOM_AUTOR
    )
    d2 = baker.make(
        DefinicjaRaportu, slug="raport-b", poziom=DefinicjaRaportu.POZIOM_AUTOR
    )
    c1, c2 = form_class_dla(d1), form_class_dla(d2)

    # rozne full_name (formdefaults kluczuje po module.ClassName)
    assert c1.__name__ == "RaportForm_raport_a"
    assert c2.__name__ == "RaportForm_raport_b"
    assert c1.__module__ == c2.__module__ == "nowe_raporty.forms_dynamiczne"
    # pole obiektu obecne dla poziomu autor
    assert "obiekt" in c1.base_fields


@pytest.mark.django_db
def test_uczelnia_bez_pola_obiektu():
    d = baker.make(
        DefinicjaRaportu, slug="raport-u", poziom=DefinicjaRaportu.POZIOM_UCZELNIA
    )
    assert "obiekt" not in form_class_dla(d).base_fields


@pytest.mark.django_db
def test_generyczny_formularz_renderuje_sie(webtest_app):
    seed_default_reports()  # raport-autorow -> WSZYSCY (anonim widzi)
    res = webtest_app.get(reverse("nowe_raporty:raport_form", args=["raport-autorow"]))
    assert res.status_code == 200


@pytest.mark.django_db
def test_kilka_raportow_na_tym_samym_poziomie(webtest_app):
    seed_default_reports()
    report = DefinicjaRaportu.objects.get(slug="raport-autorow").report
    baker.make(
        DefinicjaRaportu,
        slug="raport-autorow-drugi",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=report,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY,
        aktywny=True,
    )
    for slug in ("raport-autorow", "raport-autorow-drugi"):
        res = webtest_app.get(reverse("nowe_raporty:raport_form", args=[slug]))
        assert res.status_code == 200


@pytest.mark.django_db
def test_generyczny_generuj_renderuje(webtest_app, typy_odpowiedzialnosci):
    seed_default_reports()
    autor = baker.make(Autor)
    res = webtest_app.get(
        reverse(
            "nowe_raporty:raport_generuj", args=["raport-autorow", autor.pk, 2020, 2020]
        )
    )
    assert res.status_code == 200
    assert "Publikacje w czasopismach naukowych" in res.text


@pytest.mark.django_db
def test_generyczny_uczelnia_generuj_bez_pk(webtest_app, uczelnia):
    seed_default_reports()
    # raport-uczelni: domyslnie POKAZUJ_NIGDY -> aktywny=False; wlaczamy go
    d = DefinicjaRaportu.objects.get(slug="raport-uczelni")
    d.aktywny = True
    d.poziom_dostepu = DefinicjaRaportu.DOSTEP_WSZYSCY
    d.save()
    res = webtest_app.get(
        reverse(
            "nowe_raporty:raport_generuj_uczelnia", args=["raport-uczelni", 2020, 2020]
        )
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_generyczny_niewidoczny_404_dla_zalogowanego(generuj_raporty_app):
    report = baker.make("flexible_reports.Report", slug="raport-x")
    baker.make(
        DefinicjaRaportu,
        slug="raport-x",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=report,
        aktywny=False,
    )
    generuj_raporty_app.get(
        reverse("nowe_raporty:raport_form", args=["raport-x"]), status=404
    )


@pytest.mark.django_db
def test_nazwa_pliku_eksportu_opisowa(webtest_app, typy_odpowiedzialnosci):
    seed_default_reports()
    autor = baker.make(Autor, nazwisko="Marańda", imiona="Ewa")  # polskie znaki
    res = webtest_app.get(
        reverse(
            "nowe_raporty:raport_generuj",
            args=["raport-autorow", autor.pk, 2018, 2020],
        )
        + "?_export=xlsx"
    )
    cd = res.headers["Content-Disposition"]
    assert cd.startswith("attachment")
    # opisowa nazwa: typ raportu + zakres lat + rozszerzenie (NIE sam rok z URL-a)
    assert "Raport" in cd
    assert "2018-2020" in cd
    assert ".xlsx" in cd


@pytest.mark.django_db
def test_create_entries_rejestruje_formdefaults_per_definicja():
    from formdefaults.models import FormRepresentation

    from nowe_raporty.apps import create_entries

    seed_default_reports()
    create_entries(sender=None)

    # kazda definicja ma wlasny FormRepresentation (full_name per slug)
    assert FormRepresentation.objects.filter(
        full_name="nowe_raporty.forms_dynamiczne.RaportForm_raport_autorow"
    ).exists()
    assert FormRepresentation.objects.filter(
        full_name="nowe_raporty.forms_dynamiczne.RaportForm_raport_uczelni"
    ).exists()
