# -*- encoding: utf-8 -*-

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls.base import reverse

from bpp.models.fields import OpcjaWyswietlaniaField


@pytest.mark.parametrize(
    "attr,s",
    [("pokazuj_punktacje_wewnetrzna", "Punktacja wewnętrzna"),
     ('pokazuj_index_copernicus', "Index Copernicus"),
     ])
def test_uczelnia_praca_pokazuj(uczelnia, wydawnictwo_ciagle, attr, s, client):
    url = reverse("bpp:browse_praca",
                  args=(
                      ContentType.objects.get(
                          app_label="bpp",
                          model="wydawnictwo_ciagle").pk,
                      wydawnictwo_ciagle.pk)
                  )

    setattr(uczelnia, attr, True)
    uczelnia.save()
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert s in res.rendered_content

    setattr(uczelnia, attr, False)
    uczelnia.save()
    res = client.get(url, follow=True)
    assert res.status_code == 200
    assert s not in res.rendered_content


@pytest.mark.parametrize(
    "attr,s",
    [("pokazuj_status_korekty", "Status"),
     ("pokazuj_praca_recenzowana", "Praca recenzowana")]
)
def test_uczelnia_praca_pokazuj_pozostale(uczelnia, wydawnictwo_ciagle, client,
                                          admin_client, attr, s):
    url = reverse("bpp:browse_praca",
                  args=(
                      ContentType.objects.get(
                          app_label="bpp",
                          model="wydawnictwo_ciagle").pk,
                      wydawnictwo_ciagle.pk))

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()

    res = client.get(url, follow=True)
    assert s in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s in res.rendered_content

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()

    res = client.get(url, follow=True)
    assert s not in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s in res.rendered_content

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()

    res = client.get(url, follow=True)
    assert s not in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s not in res.rendered_content


lista_stron_raportow = [
    ('pokazuj_ranking_autorow', "ranking-autorow"),
    ('pokazuj_raport_autorow', "nowe_raporty/autor"),
    ('pokazuj_raport_jednostek', "nowe_raporty/jednostka"),
    ('pokazuj_raport_wydzialow', "nowe_raporty/wydzial"),
    ('pokazuj_raport_dla_komisji_centralnej',
     "raporty/dla-komisji-centralnej"),
]


@pytest.mark.parametrize("attr,s", lista_stron_raportow)
def test_uczelnia_pokazuj_menu_zawsze(uczelnia, attr, s, client, admin_client):
    url = "/"

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()

    res = client.get(url, follow=True)
    assert s in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s in res.rendered_content


@pytest.mark.parametrize("attr,s", lista_stron_raportow)
def test_uczelnia_pokazuj_menu_zalogowani(uczelnia, attr, s, client, admin_client):
    url = "/"

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()

    res = client.get(url, follow=True)
    assert s not in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s in res.rendered_content


@pytest.mark.parametrize("attr,s", lista_stron_raportow)
def test_uczelnia_pokazuj_menu_nigdy(uczelnia, attr, s, client, admin_client):
    url = "/"

    setattr(uczelnia, attr, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()

    res = client.get(url, follow=True)
    assert s not in res.rendered_content

    res = admin_client.get(url, follow=True)
    assert s not in res.rendered_content
