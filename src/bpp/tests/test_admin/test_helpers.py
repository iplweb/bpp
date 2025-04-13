import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_poszukaj_duplikatu_pola_www_i_ewentualnie_zmien_prosty(
    wydawnictwo_ciagle, admin_app, zrodlo
):
    wydawnictwo_ciagle.www = "https://onet.pl/"
    wydawnictwo_ciagle.save()

    drugie_ciagle = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)

    res = admin_app.get(
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=(drugie_ciagle.pk,))
    )
    res.forms["wydawnictwo_ciagle_form"]["www"] = "https://onet.pl/"
    res = res.forms["wydawnictwo_ciagle_form"].submit().maybe_follow()
    drugie_ciagle.refresh_from_db()

    assert drugie_ciagle.www
    assert wydawnictwo_ciagle.www
    assert drugie_ciagle.www != wydawnictwo_ciagle.www

    assert "Aby uniknąć zdublowania".encode() in res.content


@pytest.mark.django_db
def test_poszukaj_duplikatu_pola_www_i_ewentualnie_zmien_alternatywa(
    wydawnictwo_ciagle, admin_app, zrodlo
):
    wydawnictwo_ciagle.www = "https://onet.pl/"
    wydawnictwo_ciagle.save()

    drugie_ciagle = baker.make(
        Wydawnictwo_Ciagle, zrodlo=zrodlo, www="https://onet.pl/"
    )

    res = admin_app.get(
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=(drugie_ciagle.pk,))
    )
    res = res.forms["wydawnictwo_ciagle_form"].submit().maybe_follow()
    drugie_ciagle.refresh_from_db()

    assert drugie_ciagle.www
    assert wydawnictwo_ciagle.www
    assert drugie_ciagle.www != wydawnictwo_ciagle.www
    assert "Aby uniknąć zdublowania".encode() in res.content
