# -*- encoding: utf-8 -*-
from urllib.parse import urlencode

import pytest
from django.core.exceptions import ValidationError
from django.urls.base import reverse

from raport_slotow import const
from raport_slotow.views import SESSION_KEY

from django.contrib.contenttypes.models import ContentType

from bpp.models import Uczelnia
from bpp.models.const import DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY, NAJWIEKSZY_REKORD
from bpp.models.fields import OpcjaWyswietlaniaField
from bpp.tests import browse_praca_url, normalize_html


@pytest.mark.parametrize(
    "attr,s",
    [
        ("pokazuj_punktacje_wewnetrzna", "Punktacja wewnętrzna"),
        ("pokazuj_index_copernicus", "Index Copernicus"),
    ],
)
def test_uczelnia_praca_pokazuj(uczelnia, wydawnictwo_ciagle, attr, s, client):
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
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
    [
        ("pokazuj_status_korekty", "Status"),
        ("pokazuj_praca_recenzowana", "Praca recenzowana"),
    ],
)
def test_uczelnia_praca_pokazuj_pozostale(
    uczelnia, wydawnictwo_ciagle, client, admin_client, attr, s
):
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
    )

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
    ("pokazuj_ranking_autorow", "ranking-autorow"),
    ("pokazuj_raport_autorow", "nowe_raporty/autor"),
    ("pokazuj_raport_jednostek", "nowe_raporty/jednostka"),
    ("pokazuj_raport_wydzialow", "nowe_raporty/wydzial"),
    ("pokazuj_raport_dla_komisji_centralnej", "raporty/dla-komisji-centralnej"),
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


@pytest.mark.django_db
def test_pokazuj_tabele_slotow_na_stronie_rekordu(
    uczelnia, admin_client, client, praca_z_dyscyplina
):
    url = browse_praca_url(praca_z_dyscyplina)

    S = "Punktacja dyscyplin i sloty"

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.save()

    res = client.get(url)
    assert S in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = (
        OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    )
    uczelnia.save()

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S in res.rendered_content

    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = (
        OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    )
    uczelnia.save()

    res = client.get(url)
    assert S not in res.rendered_content
    res = admin_client.get(url)
    assert S not in res.rendered_content


@pytest.mark.parametrize(
    "poszukiwany_ciag,atrybut_uczelni",
    [
        ("raport slotów - autor", "pokazuj_raport_slotow_autor"),
        ("raport slotów - uczelnia", "pokazuj_raport_slotow_uczelnia"),
        ("raport slotów - zerowy", "pokazuj_raport_slotow_zerowy"),
    ],
)
@pytest.mark.django_db
def test_pokazuj_raport_slotow_menu_na_glownej(
    uczelnia, admin_client, client, poszukiwany_ciag, atrybut_uczelni, db
):
    url = reverse("bpp:browse_uczelnia", args=(uczelnia.slug,))
    S = poszukiwany_ciag

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()

    res = client.get(url)
    assert S not in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S in normalize_html(res.rendered_content)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()

    res = client.get(url)
    assert S not in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S not in normalize_html(res.rendered_content)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()

    res = client.get(url)
    assert S in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S in normalize_html(res.rendered_content)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE)
    uczelnia.save()

    res = client.get(url)
    assert S not in normalize_html(res.rendered_content)
    res = admin_client.get(url)
    assert S in normalize_html(res.rendered_content)


@pytest.mark.parametrize(
    "nazwa_url,atrybut_uczelni,params",
    [
        ("raport_slotow:index", "pokazuj_raport_slotow_autor", {}),
        ("raport_slotow:raport-slotow-zerowy", "pokazuj_raport_slotow_zerowy", {}),
        (
            "raport_slotow:raport",
            "pokazuj_raport_slotow_autor",
            {},
        ),
        (
            "raport_slotow:lista-raport-slotow-uczelnia",
            "pokazuj_raport_slotow_uczelnia",
            {},
        ),
        (
            "raport_slotow:lista-raport-slotow-uczelnia",
            "pokazuj_raport_slotow_uczelnia",
            {"od_roku": 2000, "do_roku": 2000, "maksymalny_slot": 1, "_export": "html"},
        ),
    ],
)
@pytest.mark.django_db
def test_pokazuj_raport_slotow_czy_mozna_kliknac(
    uczelnia, admin_client, client, autor, nazwa_url, atrybut_uczelni, params
):
    url = reverse(nazwa_url)
    if nazwa_url == "raport_slotow:raport":
        dane_raportu = {
            "obiekt": autor.pk,
            "od_roku": 2016,
            "do_roku": 2017,
            "dzialanie": const.DZIALANIE_SLOT,
            "minimalny_pk": 0,
            "slot": 19,
            "_export": "html",
        }

        for c in admin_client, client:
            s = c.session
            s.update({SESSION_KEY: dane_raportu})
            s.save()

    if params:
        url += "?" + urlencode(params)

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM)
    uczelnia.save()

    res = client.get(url)
    assert res.status_code == 302
    res = admin_client.get(url)
    assert res.status_code == 200

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_NIGDY)
    uczelnia.save()

    res = client.get(url)
    assert res.status_code == 404
    res = admin_client.get(url)
    assert res.status_code == 404

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE)
    uczelnia.save()

    res = client.get(url)
    assert res.status_code == 302
    res = admin_client.get(url)
    assert res.status_code == 200

    setattr(uczelnia, atrybut_uczelni, OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE)
    uczelnia.save()

    if atrybut_uczelni == "pokazuj_raport_slotow_uczelnia":
        # dla opcji "pokazuj raport slotów uczelnia" login jest zawsze wymagany
        pass
    else:

        res = client.get(url)
        assert res.status_code == 200
        res = admin_client.get(url)
        assert res.status_code == 200


def test_uczelnia_obca_jednostka(uczelnia, jednostka, obca_jednostka):
    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()

    uczelnia.obca_jednostka = jednostka
    with pytest.raises(ValidationError):
        uczelnia.save()


def test_uczelnia_ukryte_statusy(uczelnia, przed_korekta, po_korekcie):
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    uczelnia.ukryj_status_korekty_set.create(status_korekty=po_korekcie)

    assert przed_korekta.pk in uczelnia.ukryte_statusy("sloty")
    assert po_korekcie.pk in uczelnia.ukryte_statusy("sloty")


def test_uczelnia_do_roku_default(uczelnia, wydawnictwo_zwarte):
    wydawnictwo_zwarte.rok = 3000
    wydawnictwo_zwarte.save()

    uczelnia.metoda_do_roku_formularze = DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY
    uczelnia.save()

    assert Uczelnia.objects.do_roku_default() != 3000

    uczelnia.metoda_do_roku_formularze = NAJWIEKSZY_REKORD
    uczelnia.save()

    assert Uczelnia.objects.do_roku_default() == 3000
