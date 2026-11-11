"""Strony źródła i wydawcy: sekcje „Najczęściej publikujący autorzy”
i „Jednostki”, znaczek poziomu wydawcy oraz ujednolicone formularze
wyszukiwania (źródło, wydawca, jednostka)."""

import json
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import (
    Autor,
    Jednostka,
    Status_Korekty,
    Ukryj_Status_Korekty,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.wydawca import Poziom_Wydawcy
from bpp.multiseek_registry import registry
from bpp.sekcje_zrodla_wydawcy import (
    aktualny_poziom_wydawcy,
    najczesciej_publikujacy_autorzy,
    najczestsze_jednostki,
    sekcje_wydawcy,
    sekcje_zrodla,
)

pytestmark = pytest.mark.django_db


def _request(user=None):
    req = RequestFactory().get("/")
    req.user = user or AnonymousUser()
    return req


def _ciagle(zrodlo, autorzy_jednostki, status=None):
    praca = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Praca",
        rok=2020,
        zrodlo=zrodlo,
        punkty_kbn=Decimal("0"),
        impact_factor=Decimal("0"),
        **({"status_korekty": status} if status else {}),
    )
    for autor, jednostka in autorzy_jednostki:
        praca.dodaj_autora(autor, jednostka)
    return praca


def _autor(nazwisko, **kw):
    return baker.make(Autor, nazwisko=nazwisko, imiona="Jan", **kw)


@pytest.fixture
def dorobek_zrodla(uczelnia, zrodlo, jednostka, jednostka_podrzedna, denorms):
    """Kowalski: 3 prace, Nowak: 2, Wiśniewski: 1; praca w innym źródle
    się nie liczy."""
    kowalski = _autor("Kowalski")
    nowak = _autor("Nowak")
    wisniewski = _autor("Wiśniewski")
    _ciagle(zrodlo, [(kowalski, jednostka), (nowak, jednostka_podrzedna)])
    _ciagle(zrodlo, [(kowalski, jednostka), (nowak, jednostka)])
    _ciagle(zrodlo, [(kowalski, jednostka_podrzedna), (wisniewski, jednostka)])
    inne = baker.make("bpp.Zrodlo", nazwa="Inne źródło")
    _ciagle(inne, [(wisniewski, jednostka), (nowak, jednostka_podrzedna)])
    denorms.flush()
    return kowalski, nowak, wisniewski


def test_top_autorzy_kolejnosc_i_liczby(dorobek_zrodla, zrodlo):
    kowalski, nowak, wisniewski = dorobek_zrodla
    wynik = najczesciej_publikujacy_autorzy(
        {"rekord__zrodlo_id": zrodlo.pk}, _request()
    )
    assert [(w["autor"], w["liczba"]) for w in wynik] == [
        (kowalski, 3),
        (nowak, 2),
        (wisniewski, 1),
    ]


def test_top_autorzy_limit(dorobek_zrodla, zrodlo):
    wynik = najczesciej_publikujacy_autorzy(
        {"rekord__zrodlo_id": zrodlo.pk}, _request(), limit=1
    )
    assert [w["liczba"] for w in wynik] == [3]


def test_top_autorzy_pomija_ukrytych_w_rankingu(dorobek_zrodla, zrodlo, admin_user):
    kowalski, nowak, _wisniewski = dorobek_zrodla
    Autor.objects.filter(pk=kowalski.pk).update(pokazuj_w_rankingu=False)

    anonim = najczesciej_publikujacy_autorzy(
        {"rekord__zrodlo_id": zrodlo.pk}, _request()
    )
    assert kowalski not in [w["autor"] for w in anonim]
    assert anonim[0]["autor"] == nowak

    redakcja = najczesciej_publikujacy_autorzy(
        {"rekord__zrodlo_id": zrodlo.pk}, _request(admin_user)
    )
    assert redakcja[0]["autor"] == kowalski


def test_top_pomija_prace_o_ukrytym_statusie(
    uczelnia, zrodlo, jednostka, denorms, admin_user
):
    ukryty = baker.make(Status_Korekty, nazwa="ukryty-test")
    Ukryj_Status_Korekty.objects.create(
        uczelnia=uczelnia, status_korekty=ukryty, podglad=True
    )
    autor = _autor("Ukryty")
    _ciagle(zrodlo, [(autor, jednostka)], status=ukryty)
    denorms.flush()

    assert sekcje_zrodla(zrodlo, _request()) == {
        "top_autorzy": [],
        "top_jednostki": [],
    }
    redakcja = sekcje_zrodla(zrodlo, _request(admin_user))
    assert [w["autor"] for w in redakcja["top_autorzy"]] == [autor]
    assert [j["pk"] for j in redakcja["top_jednostki"]] == [jednostka.pk]


def test_top_jednostki_tylko_widoczne_i_bez_obcej(
    dorobek_zrodla, zrodlo, jednostka, jednostka_podrzedna, obca_jednostka, denorms
):
    ukryta = baker.make(
        Jednostka,
        nazwa="Ukryta",
        skrot="UKR",
        uczelnia=jednostka.uczelnia,
        widoczna=False,
    )
    obcy, z_ukrytej = _autor("Obcy"), _autor("Zukrytej")
    for _ in range(5):
        praca = _ciagle(zrodlo, [(z_ukrytej, ukryta)])
        praca.dodaj_autora(obcy, obca_jednostka, afiliuje=False)
    denorms.flush()

    wynik = najczestsze_jednostki({"rekord__zrodlo_id": zrodlo.pk}, _request())
    # jednostka: prace 1, 2, 3; podrzędna: prace 1, 3.
    assert [(j["pk"], j["liczba"]) for j in wynik] == [
        (jednostka.pk, 3),
        (jednostka_podrzedna.pk, 2),
    ]
    assert wynik[0]["slug"] == jednostka.slug


def test_sekcje_zrodla_liczba_zapytan(
    dorobek_zrodla, zrodlo, uczelnia, django_assert_max_num_queries
):
    # Uczelnia + ukryte statusy (memoizowane na request), ranking autorów,
    # obiekty autorów, ranking jednostek — stała liczba, bez N+1.
    req = _request()
    with django_assert_max_num_queries(6):
        sekcje_zrodla(zrodlo, req)


def test_strona_zrodla_sekcje_i_linki(client, dorobek_zrodla, zrodlo, jednostka):
    kowalski, nowak, wisniewski = dorobek_zrodla
    # Nowak: strona schowana (wymaga też ukrycia w wyszukiwaniu i indeksie)
    # — ani ludzika, ani linku do wyszukiwania. Wiśniewski: tylko ukryty
    # w wyszukiwaniu — ludzik zostaje, nazwisko bez linku.
    Autor.objects.filter(pk=nowak.pk).update(
        pokazuj_strone_autora=False,
        pokazuj_w_wyszukiwaniu=False,
        pokazuj_w_indeksie=False,
    )
    Autor.objects.filter(pk=wisniewski.pk).update(pokazuj_w_wyszukiwaniu=False)

    html = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))).content
    html = html.decode()

    assert "Najczęściej publikujący autorzy" in html
    # Kolejność wg liczby prac.
    assert html.index("Kowalski") < html.index("Nowak") < html.index("Wiśniewski")
    assert "(3)" in html
    # Klik w nazwisko = POST autor + źródło.
    assert f'name="autor" value="{kowalski.pk}"' in html
    assert f'name="autor" value="{nowak.pk}"' not in html
    assert f'name="autor" value="{wisniewski.pk}"' not in html
    # Ludzik tylko dla autorów z publiczną stroną.
    assert kowalski.get_absolute_url() in html
    assert wisniewski.get_absolute_url() in html
    assert f'Strona autora: {nowak}"' not in html
    # Jednostki z linkiem do strony jednostki.
    assert reverse("bpp:browse_jednostka", args=(jednostka.slug,)) in html


def test_build_search_autor_w_zrodle(client, dorobek_zrodla, zrodlo):
    """POST z sekcji autorów (autor + źródło) daje prace autora w źródle."""
    _kowalski, nowak, _wisniewski = dorobek_zrodla
    resp = client.post(
        reverse("bpp:browse_build_search"),
        {"autor": nowak.pk, "zrodlo": zrodlo.pk, "suggested-title": "x"},
    )
    assert resp.status_code == 302
    dane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    assert registry.get_query_for_model(dane).count() == 2


@pytest.fixture
def wydawca_z_aliasem(uczelnia, jednostka, denorms):
    glowny = baker.make(Wydawca, nazwa="Wydawnictwo Główne")
    alias = baker.make(Wydawca, nazwa="Wyd. Gł.", alias_dla=glowny)
    autor = _autor("Zwarty")
    for w in (glowny, alias):
        p = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="K", rok=2021, wydawca=w)
        p.dodaj_autora(autor, jednostka)
    denorms.flush()
    return glowny, autor


def test_sekcje_wydawcy_licza_prace_aliasow(wydawca_z_aliasem, jednostka):
    glowny, autor = wydawca_z_aliasem
    ctx = sekcje_wydawcy(glowny, _request())
    assert [(w["autor"], w["liczba"]) for w in ctx["top_autorzy"]] == [(autor, 2)]
    assert [(j["pk"], j["liczba"]) for j in ctx["top_jednostki"]] == [(jednostka.pk, 2)]
    assert ctx["aktualny_poziom"] is None


def test_strona_wydawcy_sekcje_poziom_i_formularz(client, wydawca_z_aliasem):
    glowny, autor = wydawca_z_aliasem
    baker.make(Poziom_Wydawcy, wydawca=glowny, rok=2023, poziom=1)
    baker.make(Poziom_Wydawcy, wydawca=glowny, rok=2025, poziom=2)

    html = client.get(glowny.get_absolute_url()).content.decode()

    assert "Poziom II (2025)" in html
    assert "Najczęściej publikujący autorzy" in html
    assert f'name="autor" value="{autor.pk}"' in html
    # Formularz w nowym stylu: chipy typów, lata, tytuł wyników.
    assert 'name="typ" value="publikacje"' in html
    assert 'name="rok" value="2021"' in html
    assert 'name="suggested-title"' in html
    assert "autor-page__search-stopka" in html


@pytest.mark.parametrize(
    "wpisy,oczekiwany",
    [
        ([], None),
        ([(2023, 2), (2025, 1)], {"rok": 2025, "poziom": 1, "rzymski": "I"}),
        # Najnowszy rok bez poziomu — wydawca wypadł z wykazu.
        ([(2023, 2), (2025, None)], None),
    ],
)
def test_aktualny_poziom_wydawcy(db, wpisy, oczekiwany):
    wydawca = baker.make(Wydawca, nazwa="W")
    for rok, poziom in wpisy:
        baker.make(Poziom_Wydawcy, wydawca=wydawca, rok=rok, poziom=poziom)
    assert aktualny_poziom_wydawcy(wydawca) == oczekiwany


def _formularz_wyszukiwania(html):
    """Fragment HTML formularza wyszukiwarki (od nagłówka do końca form)."""
    start = html.index("autor-page__search-container")
    return html[start : html.index("</form>", start)]


def test_formularz_zrodla_nowy_styl(client, dorobek_zrodla, zrodlo):
    html = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,))).content
    form = _formularz_wyszukiwania(html.decode())
    assert f'name="zrodlo" value="{zrodlo.pk}"' in form
    assert 'name="typ"' in form
    assert 'name="rok" value="2020"' in form
    # Selektor lat wewnątrz <form>.
    assert "data-zakres-lat" in form
    assert form.count('name="suggested-title"') == 1
    assert "autor-page__filtr" in form


def test_formularz_jednostki_nowy_styl(
    client, jednostka, jednostka_podrzedna, autor_jan_kowalski, autor_jan_nowak
):
    from bpp.models import Autor_Jednostka

    Autor_Jednostka.objects.create(
        autor=autor_jan_kowalski, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )
    praca = baker.make(Wydawnictwo_Ciagle, rok=2020)
    praca.dodaj_autora(autor_jan_nowak, jednostka)
    Autor_Jednostka.objects.filter(autor=autor_jan_nowak).delete()

    html = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    form = _formularz_wyszukiwania(html.content.decode())

    assert f'name="jednostka" value="{jednostka.pk}"' in form
    assert f'name="jednostka" value="{jednostka_podrzedna.pk}"' in form
    assert 'name="typ"' in form
    assert f'value="{autor_jan_kowalski.pk}"' in form
    assert "Obecni pracownicy" in form
    # Byli pracownicy w zwijanej sekcji.
    assert "<details" in form
    assert "Byli pracownicy" in form
    assert f'value="{autor_jan_nowak.pk}"' in form
    assert "data-zakres-lat" in form
    assert form.count('name="suggested-title"') == 1
