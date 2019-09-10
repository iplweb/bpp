# -*- encoding: utf-8 -*-

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls.base import reverse

from bpp.models.fields import OpcjaWyswietlaniaField
from bpp.tasks import aktualizuj_cache_rekordu
from bpp.tests import browse_praca_url


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


@pytest.fixture
def praca_z_dyscyplina(wydawnictwo_ciagle_z_autorem, dyscyplina1):
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    wca.dyscyplina_naukowa = dyscyplina1
    wca.save()
    aktualizuj_cache_rekordu(wydawnictwo_ciagle_z_autorem)
    return wydawnictwo_ciagle_z_autorem


@pytest.mark.django_db
def test_pokazuj_tabele_slotow_na_stronie_rekordu(uczelnia, admin_client, client, praca_z_dyscyplina):
    url = browse_praca_url(praca_z_dyscyplina)

    S = "Punktacja dyscyplin i sloty"

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    uczelnia.save()

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    uczelnia.save()

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S not in res.rendered_content

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()

    res = client.get(url)
    assert S in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content


@pytest.mark.django_db
def test_pokazuj_raport_slotow_menu_na_glownej(uczelnia, admin_client, client):
    url = reverse("bpp:browse_uczelnia", args=(uczelnia.slug,))
    S = "raport slot"

    uczelnia.pokazuj_raport_slotow = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    uczelnia.save()

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content

    uczelnia.pokazuj_raport_slotow = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    uczelnia.save()

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S not in res.rendered_content

    uczelnia.pokazuj_raport_slotow = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()

    res = client.get(url)
    assert S in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content


@pytest.mark.django_db
def test_pokazuj_raport_slotow_czy_mozna_kliknac(uczelnia, admin_client, client, autor):
    for url in [reverse("raport_slotow:index"),
                reverse("raport_slotow:raport", args=(autor.slug, 2000, 2010, "html"))]:
        uczelnia.pokazuj_raport_slotow = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
        uczelnia.save()

        res = client.get(url)
        assert res.status_code == 302
        res = admin_client.get(url)
        assert res.status_code == 200

        uczelnia.pokazuj_raport_slotow = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
        uczelnia.save()

        res = client.get(url)
        assert res.status_code == 404
        res = admin_client.get(url)
        assert res.status_code == 404

        uczelnia.pokazuj_raport_slotow = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        uczelnia.save()

        res = client.get(url)
        assert res.status_code == 200
        res = admin_client.get(url)
        assert res.status_code == 200
