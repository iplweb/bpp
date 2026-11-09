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
