"""Strony jednostki i źródła: wykresy w latach, selektor lat „od–do”
i (na jednostce) typy jako chipy — jak na stronie autora."""

from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Rekord, Wydawnictwo_Ciagle
from bpp.wykresy_lat import wykresy_w_latach


def _praca(rok, zrodlo=None, autorzy=(), jednostka=None, punkty="10"):
    p = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=f"Praca {rok}",
        rok=rok,
        zrodlo=zrodlo,
        punkty_kbn=Decimal(punkty),
        impact_factor=Decimal("0"),
    )
    for autor in autorzy:
        p.dodaj_autora(autor, jednostka)
    return p


@pytest.mark.django_db
def test_wykresy_w_latach_nie_dubluja_punktow_przy_wielu_autorach(
    jednostka, standard_data, denorms
):
    a1 = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="Kowalska", imiona="Anna")
    _praca(2020, autorzy=(a1, a2), jednostka=jednostka, punkty="100")
    _praca(2021, autorzy=(a1,), jednostka=jednostka, punkty="20")
    denorms.flush()

    wykresy = wykresy_w_latach(Rekord.objects.prace_jednostki(jednostka))
    po_nazwie = {w["nazwa"]: w["dane"] for w in wykresy}

    assert po_nazwie["Publikacje w latach"]["dane"] == [(2020, 1), (2021, 1)]
    assert po_nazwie["Punkty MNiSW w latach"]["dane"] == [
        (2020, Decimal("100")),
        (2021, Decimal("20")),
    ]
    # Same zera IF — wykres IF się nie pokazuje.
    assert "Impact Factor w latach" not in po_nazwie


@pytest.mark.django_db
def test_strona_jednostki_ma_wykresy_chipy_i_selektor_lat(
    client, jednostka, standard_data, denorms
):
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    _praca(2020, autorzy=(autor,), jednostka=jednostka)
    _praca(2022, autorzy=(autor,), jednostka=jednostka)
    denorms.flush()

    html = client.get(
        reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    ).content.decode()

    assert "Publikacje w latach" in html
    assert "data-zakres-lat" in html
    assert 'class="autor-page__chip"' in html
    # Formularz wykresu filtruje po jednostce (nie po autorze).
    assert f'name="jednostka" value="{jednostka.pk}"' in html
    assert 'name="typ"' in html


@pytest.mark.django_db
def test_strona_zrodla_ma_wykresy_i_selektor_lat(
    client, zrodlo, standard_data, denorms
):
    _praca(2019, zrodlo=zrodlo)
    _praca(2021, zrodlo=zrodlo)
    denorms.flush()

    url = reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))
    html = client.get(url).content.decode()

    assert "Publikacje w latach" in html
    assert "data-zakres-lat" in html
    assert f'name="zrodlo" value="{zrodlo.pk}"' in html


@pytest.mark.django_db
def test_strona_zrodla_bez_prac_bez_wykresow(client, zrodlo):
    url = reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))
    html = client.get(url).content.decode()
    assert "Publikacje w latach" not in html


@pytest.mark.django_db
def test_wykresy_zrodla_z_punktacji_czasopisma(zrodlo, standard_data, denorms):
    from bpp.models import Punktacja_Zrodla
    from bpp.wykresy_lat import wykresy_zrodla

    # Dwie prace po 10 pkt w 2021 — suma prac (20) NIE może trafić na wykres.
    _praca(2021, zrodlo=zrodlo)
    _praca(2021, zrodlo=zrodlo)
    denorms.flush()
    baker.make(
        Punktacja_Zrodla,
        zrodlo=zrodlo,
        rok=2020,
        punkty_kbn=Decimal("70"),
        impact_factor=Decimal("1.234"),
    )
    baker.make(
        Punktacja_Zrodla,
        zrodlo=zrodlo,
        rok=2021,
        punkty_kbn=Decimal("100"),
        impact_factor=Decimal("0"),
    )

    wykresy = wykresy_zrodla(zrodlo)
    po_nazwie = {w["nazwa"]: w for w in wykresy}

    assert list(po_nazwie) == [
        "Publikacje w latach",
        "Punkty MNiSW czasopisma w latach",
        "Impact Factor czasopisma w latach",
    ]
    assert po_nazwie["Publikacje w latach"]["dane"]["dane"] == [(2021, 2)]
    punkty = po_nazwie["Punkty MNiSW czasopisma w latach"]
    assert punkty["dane"]["dane"] == [(2020, Decimal("70")), (2021, Decimal("100"))]
    assert punkty["dane"]["miejsca"] == 0
    assert punkty["raport"] == "table"
    impact = po_nazwie["Impact Factor czasopisma w latach"]
    assert impact["dane"]["miejsca"] == 2
    assert impact["raport"] == "table"


@pytest.mark.django_db
def test_wykresy_zrodla_bez_punktacji_tylko_publikacje(zrodlo, standard_data, denorms):
    from bpp.models import Punktacja_Zrodla
    from bpp.wykresy_lat import wykresy_zrodla

    _praca(2021, zrodlo=zrodlo)
    denorms.flush()
    # Same zera punktacji — wykresy punktacji się nie pokazują.
    baker.make(
        Punktacja_Zrodla,
        zrodlo=zrodlo,
        rok=2021,
        punkty_kbn=Decimal("0"),
        impact_factor=Decimal("0"),
    )

    nazwy = [w["nazwa"] for w in wykresy_zrodla(zrodlo)]
    assert nazwy == ["Publikacje w latach"]


@pytest.mark.django_db
def test_strona_zrodla_pokazuje_punktacje_czasopisma(
    client, zrodlo, standard_data, denorms
):
    from bpp.models import Punktacja_Zrodla

    _praca(2021, zrodlo=zrodlo, punkty="5303")
    denorms.flush()
    baker.make(
        Punktacja_Zrodla,
        zrodlo=zrodlo,
        rok=2021,
        punkty_kbn=Decimal("140"),
        impact_factor=Decimal("3.5"),
    )

    url = reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))
    html = client.get(url).content.decode()

    assert "Punkty MNiSW czasopisma w latach" in html
    assert "Impact Factor czasopisma w latach" in html
    # Sumy punktów prac na stronie źródła już nie ma.
    assert "Punkty MNiSW w latach" not in html
    assert "5303" not in html
    assert ">140<" in html
    assert ">3,50<" in html
