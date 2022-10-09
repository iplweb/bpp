import pytest

from bpp.views.raporty import RankingAutorow


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
