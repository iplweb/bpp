import pytest
from django.urls import reverse

from rozbieznosci_dyscyplin.models import RozbieznosciView

from django.contrib.contenttypes.models import ContentType

from bpp.models import Autor_Dyscyplina

from django_bpp.selenium_util import SHORT_WAIT_TIME, wait_for, wait_for_page_load


@pytest.fixture
def zle_przypisana_praca(
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

    wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute(
        "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = %s WHERE id = %s"
        % (dyscyplina3.pk, wca.pk)
    )

    # wca.dyscyplina_naukowa_id = dyscyplina3
    #     dyscyplina_naukowa=dyscyplina3)

    return wydawnictwo_ciagle


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
        "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = %s WHERE id = %s"
        % (dyscyplina3.pk, wca.pk)
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
        "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = %s WHERE id = %s"
        % (dyscyplina1.pk, wca.pk)
    )

    assert RozbieznosciView.objects.count() == 1

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_api_rozbieznoscidyscyplin_view_niezalogowany(client, zle_przypisana_praca):
    res = client.get(reverse("rozbieznosci_dyscyplin:api-rozbieznosci-dyscyplin"))
    assert res.status_code == 302


@pytest.mark.django_db
def test_api_rozbieznoscidyscyplin_view(client, admin_user, zle_przypisana_praca):
    client.login(username=admin_user, password="password")
    res = client.get(reverse("rozbieznosci_dyscyplin:api-rozbieznosci-dyscyplin"))
    assert res.status_code == 200
    assert res.json()["data"][0]["tytul_oryginalny"].find("target") > 0

    res = client.get(
        reverse("rozbieznosci_dyscyplin:api-rozbieznosci-dyscyplin"),
        {"search[value]": "foo"},
    )
    assert res.status_code == 200


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

    client.login(username=admin_user, password="password")
    res2 = client.get(res.url)

    assert res2.status_code == 200


@pytest.mark.django_db
def test_main_view(zle_przypisana_praca, client, admin_user):
    res = client.get(reverse("rozbieznosci_dyscyplin:main-view"))
    assert res.status_code == 302

    client.login(username=admin_user, password="password")

    res = client.get(reverse("rozbieznosci_dyscyplin:main-view"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_main_view_admin(zle_przypisana_praca, admin_browser, asgi_live_server):
    with wait_for_page_load(admin_browser):
        admin_browser.visit(
            asgi_live_server.url + reverse("rozbieznosci_dyscyplin:main-view")
        )
    wait_for(lambda: "Kowalski" in admin_browser.html, max_seconds=SHORT_WAIT_TIME)
