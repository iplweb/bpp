"""Klikalne wykresy w latach i współautorzy na podstronie autora.

- klik w słupek / kolumnę roku → multiseek (autor + rok),
- klik w nazwisko współautora → multiseek ze WSPÓLNYMI pracami,
- ludzik obok nazwiska → strona współautora.
"""

import json
from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from model_bakery import baker
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import Autor
from bpp.multiseek_registry import registry
from bpp.multiseek_registry.fields.constants import UNION_NONE


class _Osoba(SimpleNamespace):
    # ``__str__`` musi być na klasie — atrybut instancji str() ignoruje.
    def __str__(self):
        return self.nazwa


AUTOR = _Osoba(pk=7, nazwa="Jan Nowak")


def _render_wykres(dane):
    maks = max((w for _r, w in dane), default=0)
    return render_to_string(
        "browse/autor_sekcje/_wykres_lata.html",
        {
            "nazwa": "Publikacje w latach",
            "dane": {"dane": dane, "maks": maks, "etykieta": "prac"},
            "autor": AUTOR,
        },
    )


@pytest.mark.parametrize("lat", [5, 12], ids=["slupkowy", "liniowy"])
def test_wykres_kazdy_rok_to_przycisk_szukania(lat):
    dane = [(2000 + i, i + 1) for i in range(lat)]
    html = _render_wykres(dane)

    assert reverse("bpp:browse_build_search") in html
    assert 'id="wykres-szukaj-publikacje-w-latach"' in html
    assert 'name="autor" value="7"' in html
    # Każdy rok ma własny przycisk spięty z formularzem atrybutem form=.
    assert html.count('form="wykres-szukaj-publikacje-w-latach"') == lat
    for rok, _w in dane:
        assert f'value="{rok}"' in html
    # Bez tokenu CSRF — inaczej strona autora wypadłaby z cache_publiczny.
    assert "csrfmiddlewaretoken" not in html


def _render_wspolautorzy(wspolautor):
    return render_to_string(
        "browse/autor_sekcje/wspolautorzy.html",
        {
            "nazwa": "Współautorzy",
            "dane": {"wspolautorzy": [{"autor": wspolautor, "liczba": 3}]},
            "autor": AUTOR,
        },
    )


def _wspolautor(**flagi):
    domyslne = {"pokazuj_strone_autora": True, "pokazuj_w_wyszukiwaniu": True}
    domyslne.update(flagi)
    return _Osoba(
        pk=11,
        get_absolute_url=lambda: "/bpp/autor/anna-kowalska/",
        nazwa="Anna Kowalska",
        **domyslne,
    )


def test_wspolautor_nazwisko_szuka_wspolnych_prac_a_ludzik_linkuje_strone():
    html = _render_wspolautorzy(_wspolautor())
    assert 'name="wspolautor" value="11"' in html
    assert 'name="autor" value="7"' in html
    assert "Jan Nowak i Anna Kowalska — wspólne prace" in html
    assert 'href="/bpp/autor/anna-kowalska/"' in html
    assert "fi-torso" in html
    assert "csrfmiddlewaretoken" not in html


def test_wspolautor_bez_strony_nie_ma_ludzika():
    html = _render_wspolautorzy(_wspolautor(pokazuj_strone_autora=False))
    assert 'name="wspolautor" value="11"' in html
    assert "/bpp/autor/anna-kowalska/" not in html
    assert 'fi-torso"' not in html


def test_wspolautor_ukryty_w_wyszukiwaniu_bez_linku_do_multiseeka():
    html = _render_wspolautorzy(_wspolautor(pokazuj_w_wyszukiwaniu=False))
    assert 'name="wspolautor"' not in html
    assert "Anna Kowalska" in html


@pytest.mark.django_db
def test_build_search_rok_z_wykresu(client):
    autor = baker.make(Autor)
    resp = client.post(
        reverse("bpp:browse_build_search"), {"autor": str(autor.pk), "rok": "2024"}
    )
    assert resp.status_code == 302
    pola = [
        f
        for f in json.loads(client.session[MULTISEEK_SESSION_KEY])["form_data"]
        if isinstance(f, dict)
    ]
    assert {f["field"] for f in pola} == {"Nazwisko i imię", "Rok"}
    assert [f["value"] for f in pola if f["field"] == "Rok"] == ["2024"]


@pytest.mark.django_db
def test_build_search_wspolautor_daje_tylko_wspolne_prace(
    client, standard_data, jednostka, denorms
):
    from bpp.models import Rekord, Wydawnictwo_Ciagle

    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    wspolautor = baker.make(Autor, nazwisko="Kowalska", imiona="Anna")
    inny = baker.make(Autor, nazwisko="Inny", imiona="Ktoś")

    wspolna = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Wspólna", rok=2020)
    wspolna.dodaj_autora(autor, jednostka)
    wspolna.dodaj_autora(wspolautor, jednostka)

    tylko_autor = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Tylko autor", rok=2020
    )
    tylko_autor.dodaj_autora(autor, jednostka)
    tylko_autor.dodaj_autora(inny, jednostka)

    tylko_wspolautor = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Tylko współautor", rok=2020
    )
    tylko_wspolautor.dodaj_autora(wspolautor, jednostka)
    denorms.flush()

    resp = client.post(
        reverse("bpp:browse_build_search"),
        {"autor": str(autor.pk), "wspolautor": str(wspolautor.pk)},
    )
    assert resp.status_code == 302

    dane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    pola = [f for f in dane["form_data"] if isinstance(f, dict)]
    assert [(f["value"], f["prev_op"]) for f in pola] == [
        (str(autor.pk), None),
        (str(wspolautor.pk), "and"),
    ]
    assert pola[1]["operator"] == str(UNION_NONE)

    qs = registry.get_query_for_model(dane)
    assert qs.model is Rekord
    assert list(qs.values_list("tytul_oryginalny", flat=True)) == ["Wspólna"]


def test_wykres_punktow_prosi_o_raport_tabela():
    html = render_to_string(
        "browse/autor_sekcje/_wykres_lata.html",
        {
            "nazwa": "Punkty MNiSW w latach",
            "dane": {"dane": [(2020, 5)], "maks": 5, "etykieta": "pkt"},
            "autor": AUTOR,
            "raport": "table",
        },
    )
    assert 'name="raport" value="table"' in html
    # Wykres publikacji (bez ``raport``) zostaje przy domyślnej liście.
    assert 'name="raport"' not in _render_wykres([(2020, 5)])


def _report_type_po_build_search(client, raport):
    autor = baker.make(Autor)
    client.post(
        reverse("bpp:browse_build_search"),
        {"autor": str(autor.pk), "rok": "2020", "raport": raport},
    )
    return json.loads(client.session[MULTISEEK_SESSION_KEY]).get("report_type")


@pytest.mark.django_db
def test_build_search_raport_tabela_dla_anonima(client, rf):
    from django.contrib.auth.models import AnonymousUser

    req = rf.get("/")
    req.user = AnonymousUser()
    dostepne = [x.id for x in registry.get_report_types(req)]

    assert _report_type_po_build_search(client, "table") == str(dostepne.index("table"))


@pytest.mark.django_db
def test_build_search_raport_niedostepny_dla_anonima_ignorowany(client):
    # „numer_list” jest niepubliczny — anonim nie ma go do wyboru.
    assert _report_type_po_build_search(client, "numer_list") is None
    assert _report_type_po_build_search(client, "nie-ma-takiego") is None


def _render_staty(n):
    wiersze = [(f"Charakter {i}", 10 - i) for i in range(n)]
    return render_to_string(
        "browse/autor_sekcje/statystyki_charakter.html",
        {
            "nazwa": "Statystyki wg charakteru",
            "dane": {"wiersze": wiersze, "suma": sum(x for _c, x in wiersze)},
            "autor": AUTOR,
        },
    )


def test_staty_do_8_pozycji_bez_rozwin():
    html = _render_staty(8)
    assert "Rozwiń" not in html
    assert "autor-page__rozwin-wiersz" not in html


def test_staty_powyzej_8_pozycji_zwija_reszte():
    html = _render_staty(11)
    assert "Rozwiń (jeszcze 3)" in html
    assert html.count('class="autor-page__rozwin-wiersz"') == 3
    assert 'id="staty-charakter-rozwin"' in html
    assert 'for="staty-charakter-rozwin"' in html
