import pytest
from django.urls import reverse
from model_bakery import baker

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
):
    jw1 = baker.make(Jednostka, wydzial=wydzial, uczelnia=uczelnia)
    jw2 = baker.make(Jednostka, wydzial=drugi_wydzial, uczelnia=uczelnia)

    autor_jan_nowak.dodaj_jednostke(jw1)
    autor_jan_kowalski.dodaj_jednostke(jw2)

    wc1 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=timezone.now().year)
    wc1.dodaj_autora(autor_jan_nowak, jw1)

    wc2 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=timezone.now().year)
    wc2.dodaj_autora(autor_jan_kowalski, jw2)

    # Wydzial 1
    res = admin_app.get(
        reverse(
            "bpp:ranking_autorow_formularz",
        )
    )
    res.forms[0]["wydzialy"].value = [
        wydzial.pk,
    ]

    result = res.forms[0].submit().maybe_follow()
    assert b"Kowalski" not in result.content
    assert b"Nowak" in result.content

    # Wydzial 2
    res = admin_app.get(
        reverse(
            "bpp:ranking_autorow_formularz",
        )
    )
    res.forms[0]["wydzialy"].value = [
        drugi_wydzial.pk,
    ]

    result = res.forms[0].submit().maybe_follow()
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
):
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

    result = res.forms[0].submit().maybe_follow()
    assert b"Kowalski" in result.content
    assert b"Nowak" in result.content
