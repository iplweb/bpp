import pytest
from django.urls import reverse
from model_bakery import baker

from ranking_autorow.forms import RankingAutorowForm
from ranking_autorow.views import RankingAutorow

from django.utils import timezone

from bpp.models import Jednostka, Wydawnictwo_Ciagle

TEST123 = "TEST123"


@pytest.mark.django_db
def test_ranking_autorow_get_queryset_prace_sa(
    wydawnictwo_ciagle_z_autorem,
    wydawnictwo_zwarte_z_autorem,
    rf,
    uczelnia,
    przed_korekta,
):
    wydawnictwo_ciagle_z_autorem.punkty_pk = 20
    wydawnictwo_ciagle_z_autorem.impact_factor = 20
    wydawnictwo_ciagle_z_autorem.status_korekty = przed_korekta
    wydawnictwo_ciagle_z_autorem.save()

    wydawnictwo_zwarte_z_autorem.impact_factor = 50
    wydawnictwo_zwarte_z_autorem.punkty_pk = 20
    wydawnictwo_zwarte_z_autorem.status_korekty = przed_korekta
    wydawnictwo_ciagle_z_autorem.save()

    r = RankingAutorow(request=rf.get("/"), kwargs=dict(od_roku=0, do_roku=3030))

    assert r.get_queryset().count() == 1

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    assert r.get_queryset().count() == 0


@pytest.mark.django_db
def test_ranking_autorow_po_typie_kbn(
    wydawnictwo_ciagle_z_autorem,
    rf,
):
    wydawnictwo_ciagle_z_autorem.punkty_pk = 20
    wydawnictwo_ciagle_z_autorem.impact_factor = 20
    wydawnictwo_ciagle_z_autorem.save()

    r = RankingAutorow(request=rf.get("/"), kwargs=dict(od_roku=0, do_roku=3030))

    assert r.get_queryset().count() == 1

    tk = wydawnictwo_ciagle_z_autorem.typ_kbn
    tk.wliczaj_do_rankingu = False
    tk.save()

    r = RankingAutorow(request=rf.get("/"), kwargs=dict(od_roku=0, do_roku=3030))

    assert r.get_queryset().count() == 0


@pytest.mark.django_db
def test_ranking_autorow_po_charakterze_formalnym(
    wydawnictwo_ciagle_z_autorem,
    rf,
):
    wydawnictwo_ciagle_z_autorem.punkty_pk = 20
    wydawnictwo_ciagle_z_autorem.impact_factor = 20
    wydawnictwo_ciagle_z_autorem.save()

    r = RankingAutorow(request=rf.get("/"), kwargs=dict(od_roku=0, do_roku=3030))

    assert r.get_queryset().count() == 1

    cf = wydawnictwo_ciagle_z_autorem.charakter_formalny
    cf.wliczaj_do_rankingu = False
    cf.save()

    r = RankingAutorow(request=rf.get("/"), kwargs=dict(od_roku=0, do_roku=3030))

    assert r.get_queryset().count() == 0


@pytest.mark.django_db
def test_ranking_autorow_bez_kol_naukowych(
    wydawnictwo_ciagle_z_autorem,
    admin_client,
    jednostka,
    rf,
    uczelnia,
):
    jednostka.rodzaj_jednostki = Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE
    jednostka.save()

    wydawnictwo_ciagle_z_autorem.punkty_pk = 20
    wydawnictwo_ciagle_z_autorem.impact_factor = 20
    wydawnictwo_ciagle_z_autorem.save()

    # domyslnie jest ranking_autorow_bez_kol_naukowych = True
    res = admin_client.get(
        reverse("bpp:ranking-autorow", args=(0, 3030)) + "?bez_kol_naukowych=True"
    )
    assert "Kowalski" not in res.rendered_content

    uczelnia.ranking_autorow_bez_kol_naukowych = False
    uczelnia.save()

    res = admin_client.get(reverse("bpp:ranking-autorow", args=(0, 3030)))
    assert "Kowalski" in res.rendered_content


@pytest.mark.django_db
def test_ranking_autorow_bez_nieaktualnych(
    wydawnictwo_ciagle_z_autorem,
    admin_client,
    autor_jan_kowalski,
):
    autor_jan_kowalski.autor_jednostka_set.all().delete()

    wydawnictwo_ciagle_z_autorem.punkty_pk = 20
    wydawnictwo_ciagle_z_autorem.impact_factor = 20
    wydawnictwo_ciagle_z_autorem.save()

    res = admin_client.get(
        reverse("bpp:ranking-autorow", args=(0, 3030)) + "?bez_nieaktualnych=False"
    )
    assert "Kowalski" in res.rendered_content

    res = admin_client.get(
        reverse("bpp:ranking-autorow", args=(0, 3030)) + "?bez_nieaktualnych=True"
    )
    assert "Kowalski" not in res.rendered_content


@pytest.mark.django_db
def test_ranking_autorow_wybor_wydzialu(
    wydzial,
    drugi_wydzial,
    autor_jan_kowalski,
    autor_jan_nowak,
    admin_app,
    uczelnia,
    typy_odpowiedzialnosci,
    rok,
):
    wydzial.zezwalaj_na_ranking_autorow = True
    wydzial.save()

    jw1 = baker.make(Jednostka, wydzial=wydzial, uczelnia=uczelnia)
    jw2 = baker.make(Jednostka, wydzial=drugi_wydzial, uczelnia=uczelnia)

    autor_jan_nowak.dodaj_jednostke(jw1)
    autor_jan_kowalski.dodaj_jednostke(jw2)

    wc1 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=timezone.now().year)
    wc1.dodaj_autora(autor_jan_nowak, jw1)

    wc2 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=timezone.now().year)
    wc2.dodaj_autora(autor_jan_kowalski, jw2)

    # Wydzial 1 - Get form and submit
    res = admin_app.get(reverse("bpp:ranking_autorow_formularz"))
    form = res.forms[0]

    # Manually set the form fields that are available
    form["od_roku"] = rok
    form["do_roku"] = rok
    # Since wydzial is a Select2 field, we may need to skip setting it in the test
    # and test the filtering via direct URL access instead

    # Test by accessing the report URL directly with parameters
    result = admin_app.get(
        reverse("bpp:ranking-autorow", args=(rok, rok)) + f"?wydzial={wydzial.pk}"
    )
    assert b"Kowalski" not in result.content
    assert b"Nowak" in result.content

    # Wydzial 2
    result = admin_app.get(
        reverse("bpp:ranking-autorow", args=(rok, rok)) + f"?wydzial={drugi_wydzial.pk}"
    )
    assert b"Kowalski" in result.content
    assert b"Nowak" not in result.content


@pytest.mark.django_db
def test_ranking_autorow_wszystkie_wydzialy(
    wydzial,
    drugi_wydzial,
    autor_jan_kowalski,
    autor_jan_nowak,
    admin_app,
    uczelnia,
    typy_odpowiedzialnosci,
    rok,
):
    wydzial.zezwalaj_na_ranking_autorow = True
    wydzial.save()

    jw1 = baker.make(Jednostka, wydzial=wydzial, uczelnia=uczelnia)
    jw2 = baker.make(Jednostka, wydzial=drugi_wydzial, uczelnia=uczelnia)

    autor_jan_nowak.dodaj_jednostke(jw1)
    autor_jan_kowalski.dodaj_jednostke(jw2)

    wc1 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=timezone.now().year)
    wc1.dodaj_autora(autor_jan_nowak, jw1)

    wc2 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=timezone.now().year)
    wc2.dodaj_autora(autor_jan_kowalski, jw2)

    res = admin_app.get(
        reverse(
            "bpp:ranking_autorow_formularz",
        )
    )

    res.forms[0]["od_roku"] = rok
    res.forms[0]["do_roku"] = rok

    result = res.forms[0].submit().maybe_follow()
    assert b"Kowalski" in result.content
    assert b"Nowak" in result.content


@pytest.mark.django_db
def test_ranking_autorow_form_jednostki_when_not_using_wydzialy(uczelnia):
    """Test that jednostki field appears and wydzialy is hidden when uzywaj_wydzialow is False"""
    # Set uczelnia to not use wydzialy
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()

    # Create test jednostki
    baker.make(
        Jednostka,
        uczelnia=uczelnia,
        widoczna=True,
        wchodzi_do_raportow=True,
        nazwa="Jednostka 1",
    )
    baker.make(
        Jednostka,
        uczelnia=uczelnia,
        widoczna=True,
        wchodzi_do_raportow=True,
        nazwa="Jednostka 2",
    )

    # Create form
    form = RankingAutorowForm(lata=[2020, 2021, 2022])

    # Check that jednostka field is present and wydzial is not
    assert "jednostka" in form.fields
    assert "wydzial" not in form.fields

    # Check that jednostka field has correct label and help text
    assert form.fields["jednostka"].label == "Ogranicz do:"
    assert "wszystkich jednostek" in form.fields["jednostka"].help_text

    # Check that rozbij_na_jednostki label is updated
    assert form.fields["rozbij_na_jednostki"].label == "Rozbij punktację na jednostki"


@pytest.mark.django_db
def test_ranking_autorow_form_both_fields_when_using_wydzialy(uczelnia, wydzial):
    """Test that both jednostki and wydzialy fields appear when uzywaj_wydzialow is True"""
    # Set uczelnia to use wydzialy
    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()

    wydzial.zezwalaj_na_ranking_autorow = True
    wydzial.save()

    # Create form
    form = RankingAutorowForm(lata=[2020, 2021, 2022])

    # Check that BOTH fields are present when using wydzialy
    assert "jednostka" in form.fields
    assert "wydzial" in form.fields

    # Check that jednostka field has correct label and help text
    assert form.fields["jednostka"].label == "Ogranicz do:"
    assert "wszystkich jednostek" in form.fields["jednostka"].help_text

    # Check that rozbij_na_jednostki label is standard
    assert (
        form.fields["rozbij_na_jednostki"].label
        == "Rozbij punktację na jednostki i wydziały"
    )


@pytest.mark.django_db
def test_ranking_autorow_view_filters_by_jednostki(
    wydawnictwo_ciagle_z_autorem,
    jednostka,
    rf,
    uczelnia,
):
    """Test that RankingAutorow view correctly filters by jednostki"""
    # Set uczelnia to not use wydzialy
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()

    # Set up jednostka
    jednostka.widoczna = True
    jednostka.wchodzi_do_raportow = True
    jednostka.save()

    # Create another jednostka
    druga_jednostka = baker.make(
        Jednostka, uczelnia=uczelnia, widoczna=True, wchodzi_do_raportow=True
    )

    # Set up publikacja
    wydawnictwo_ciagle_z_autorem.punkty_pk = 20
    wydawnictwo_ciagle_z_autorem.impact_factor = 20
    wydawnictwo_ciagle_z_autorem.save()

    # Test without jednostki filter - should return all results (no filter applied)
    request = rf.get("/")
    view = RankingAutorow(request=request, kwargs=dict(od_roku=0, do_roku=3030))
    assert view.get_queryset().count() == 1

    # Test with jednostka filter matching - should return results
    request = rf.get(f"/?jednostka={jednostka.pk}")
    view = RankingAutorow(request=request, kwargs=dict(od_roku=0, do_roku=3030))
    assert view.get_queryset().count() == 1

    # Test with jednostka filter not matching - should return no results
    request = rf.get(f"/?jednostka={druga_jednostka.pk}")
    view = RankingAutorow(request=request, kwargs=dict(od_roku=0, do_roku=3030))
    assert view.get_queryset().count() == 0


@pytest.mark.django_db
def test_ranking_autorow_context_with_jednostki(rf, uczelnia):
    """Test that context correctly includes jednostki when not using wydzialy"""
    # Set uczelnia to not use wydzialy
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()

    # Create jednostki
    j1 = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        widoczna=True,
        wchodzi_do_raportow=True,
        nazwa="Jednostka A",
    )
    baker.make(
        Jednostka,
        uczelnia=uczelnia,
        widoczna=True,
        wchodzi_do_raportow=True,
        nazwa="Jednostka B",
    )

    # Create request with jednostka filter
    request = rf.get(f"/?jednostka={j1.pk}")
    view = RankingAutorow()
    view.request = request
    view.kwargs = dict(od_roku=2020, do_roku=2022)
    view.object_list = view.get_queryset()

    # Get context
    context = view.get_context_data()

    # Check context includes jednostki
    assert "jednostki" in context
    assert len(context["jednostki"]) == 1
    assert context["jednostki"][0] == j1

    # Check subtitle is set correctly
    assert context["table_subtitle"] == "Jednostka A"
