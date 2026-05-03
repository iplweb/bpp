"""Testy widoków bazodanowych RozbieznosciView / RozbieznosciZrodelView
oraz przekierowania `redirect-to-admin`."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Dyscyplina, Dyscyplina_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView


@pytest.mark.django_db
def test_znajdz_rozbieznosci_gdy_przypisanie_autor_dyscyplina(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    assert RozbieznosciView.objects.count() == 0

    wca.dyscyplina_naukowa = dyscyplina2
    wca.save()

    assert RozbieznosciView.objects.count() == 0

    from django.db import connection

    cur = connection.cursor()
    cur.execute(
        f"UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = {dyscyplina3.pk} WHERE id = {wca.pk}"
    )

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski


@pytest.mark.django_db
def test_znajdz_rozbieznosci_bez_przypisania_autor_dyscyplina(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = {dyscyplina1.pk} WHERE id = {wca.pk}"
    )

    assert RozbieznosciView.objects.count() == 1

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_redirect_to_admin_view(wydawnictwo_ciagle, client, admin_user):
    res = client.get(
        reverse(
            "rozbieznosci_dyscyplin:redirect-to-admin",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    wydawnictwo_ciagle
                ).pk,
                "object_id": wydawnictwo_ciagle.pk,
            },
        )
    )
    assert res.status_code == 302

    client.login(username=admin_user.username, password="password")
    res2 = client.get(res.url)

    assert res2.status_code == 200


def test_RozbieznosciZrodelView(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    assert RozbieznosciZrodelView.objects.count() == 0

    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc: Wydawnictwo_Ciagle = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(
        autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1
    )  # Zrodlo nie ma tej dysc.

    assert RozbieznosciZrodelView.objects.count() == 1

    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina1)
    assert RozbieznosciZrodelView.objects.count() == 0


@pytest.mark.django_db
def test_get_wydawnictwo_autor_obj_returns_author_record(zle_przypisana_praca):
    """Test get_wydawnictwo_autor_obj returns the author-publication record."""
    rozbieznosc = RozbieznosciView.objects.first()
    assert rozbieznosc is not None

    wca = rozbieznosc.get_wydawnictwo_autor_obj()
    assert wca is not None
    assert wca.autor == rozbieznosc.autor
