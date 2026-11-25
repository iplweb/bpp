from urllib.parse import quote

import pytest
from django.urls import Resolver404, resolve, reverse
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
def test_generyczny_formularz_renderuje_sie(webtest_app, uczelnia):
    seed_default_reports()  # raport-autorow -> WSZYSCY (anonim widzi)
    res = webtest_app.get(reverse("nowe_raporty:raport_form", args=["raport-autorow"]))
    assert res.status_code == 200


@pytest.mark.django_db
def test_formularz_prefiluje_obiekt_z_querystringu(webtest_app):
    # „Raport szczegółowy" ze strony autora przekazuje ?obiekt=<pk> — pole
    # Select2 musi pokazać wybranego autora (DAL renderuje wybraną opcję).
    seed_default_reports()
    autor = baker.make(Autor, nazwisko="Wybralski", imiona="Jan")
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    res = webtest_app.get(url + f"?obiekt={autor.pk}")
    assert res.status_code == 200
    # Wybrana opcja w <select> obiektu: value=pk + nazwisko autora.
    assert f'value="{autor.pk}"' in res.text
    assert "Wybralski" in res.text


@pytest.mark.django_db
def test_formularz_zly_obiekt_w_querystringu_nie_wywala(webtest_app):
    seed_default_reports()
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    res = webtest_app.get(url + "?obiekt=999999")
    assert res.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "obiekt",
    [
        "vS04D",
        "1abc",
        "-1",
        "1.5",
        "%20",
        # '²'.isdigit() jest True, a int('²') rzuca ValueError.
        quote("²"),
        # Powyżej 4300 cyfr int() rzuca ValueError (limit konwersji).
        "9" * 4301,
        # Poza zakresem ``integer`` PostgreSQL.
        "2147483648",
        "99999999999",
    ],
)
def test_formularz_nienumeryczny_obiekt_w_querystringu_nie_wywala(
    webtest_app, obiekt
):
    # ?obiekt=<nie-liczba> wywalał 500 (ValueError: Field 'id' expected
    # a number) — błędny parametr od klienta ma dać formularz bez wyboru.
    seed_default_reports()
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    res = webtest_app.get(url + f"?obiekt={obiekt}")
    assert res.status_code == 200


@pytest.mark.django_db
def test_formularz_cyfry_unicode_w_obiekcie_nie_wybieraja_autora(webtest_app):
    # int("١٢") == 12 — cyfry arabsko-indyjskie wybierały prawdziwego autora
    # o pk 12. Dwóch autorów, bo przy jednym widok celowo wybiera go sam.
    seed_default_reports()
    baker.make(Autor, pk=12, nazwisko="Dwunasty", imiona="Jan")
    baker.make(Autor, pk=13, nazwisko="Trzynasty", imiona="Jan")
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    res = webtest_app.get(url + "?obiekt=" + quote("١٢"))
    assert res.status_code == 200
    assert res.context["form"].initial.get("obiekt") is None
    assert 'value="12"' not in res.text
    assert "Dwunasty" not in res.text

    # Kontrola: ten sam autor podany cyframi ASCII jest wybierany.
    res = webtest_app.get(url + "?obiekt=12")
    assert res.context["form"].initial.get("obiekt").pk == 12


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pk",
    # Ścieżki >1024 znaków odcina wcześniej middleware (444), więc długi
    # ciąg przez cały stos testujemy na 900 cyfrach, a 4301 — w resolverze.
    [quote("²"), quote("١٢"), "9" * 11, "9" * 900, "2147483648"],
)
def test_generuj_zly_pk_w_adresie_daje_404(webtest_app, pk):
    # Wzorzec ``\d+`` przepuszczał cyfry Unicode i dowolnie długie ciągi
    # do ORM (ValueError = 500). Zły pk w adresie generowania = 404.
    seed_default_reports()
    baker.make(Autor, pk=12, nazwisko="Dwunasty", imiona="Jan")
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    webtest_app.get(f"{url}{pk}/2020/2020/", status=404)


@pytest.mark.django_db
@pytest.mark.parametrize("rok", [quote("²"), "9" * 900])
def test_generuj_zly_rok_w_adresie_daje_404(webtest_app, rok):
    seed_default_reports()
    url = reverse("nowe_raporty:raport_form", args=["raport-uczelni"])
    webtest_app.get(f"{url}{rok}/2020/", status=404)


@pytest.mark.parametrize(
    "ogon",
    [
        "9" * 4301 + "/2020/2020/",
        "12/" + "9" * 4301 + "/2020/",
        "²/2020/2020/",
        "١٢/2020/2020/",
        "²/2020/",
    ],
)
def test_generuj_resolver_odrzuca_zly_pk_i_rok(ogon):
    # Bez middleware (ten tnie ścieżki >1024 znaków): sam wzorzec URL nie może
    # dopasować cyfr Unicode ani ciągów dłuższych niż zakres ``integer``.
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    with pytest.raises(Resolver404):
        resolve(url + ogon)


@pytest.mark.django_db
def test_kilka_raportow_na_tym_samym_poziomie(webtest_app, uczelnia):
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
def test_create_entries_rejestruje_formdefaults_per_definicja(uczelnia):
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
