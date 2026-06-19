"""Testy kafelkowego edytora układu profilu autora (widget + form, §3.2).

Edytor zastępuje surowy textarea JSON w ``UczelniaAdmin`` przyjaznym widgetem
kafelkowym (drag-drop). Unit-testy skupiają się na round-tripie danych:
``clean_uklad_profilu_autora`` sanityzuje przez ``waliduj_uklad``, a
``render`` rysuje kafelek dla KAŻDEJ sekcji katalogu.
"""

import json

import pytest
from django.urls import reverse

from bpp.admin.uczelnia import UczelniaAdminForm
from bpp.admin.widgets.uklad_profilu import EdytorUkladuWidget
from bpp.models import Uczelnia
from bpp.profil_autora import (
    DOMYSLNY_LIMIT,
    KATALOG_SEKCJI,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WYKRES_LATA,
    rozwiaz_uklad,
)


def _clean_uklad(posted_value):
    """Uruchom samą walidację pola układu (bez wymagania całego formularza).

    ``full_clean`` populuje ``cleaned_data`` dla pól, które przeszły walidację
    pola, niezależnie od innych wymaganych pól modelu.
    """
    form = UczelniaAdminForm(
        data={"uklad_profilu_autora": posted_value},
        instance=Uczelnia(),
    )
    form.is_valid()  # wymusza full_clean, w tym clean_uklad_profilu_autora
    assert "uklad_profilu_autora" not in form.errors, form.errors
    return form.cleaned_data["uklad_profilu_autora"]


def test_clean_parsuje_zserializowany_json_i_zachowuje_kolejnosc():
    posted = json.dumps(
        [
            {"klucz": KLUCZ_WYKRES_LATA, "widoczna": False, "limit": None},
            {"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 30},
            {"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "widoczna": True, "limit": None},
        ]
    )
    wynik = _clean_uklad(posted)

    klucze = [p["klucz"] for p in wynik]
    assert klucze == [
        KLUCZ_WYKRES_LATA,
        KLUCZ_NAJLEPSZE_PK,
        KLUCZ_STATYSTYKI_CHARAKTER,
    ]
    assert wynik[0]["widoczna"] is False
    assert wynik[1]["limit"] == 30
    # sekcja bez limitu → None nawet jak ktoś podsunął wartość
    assert wynik[2]["limit"] is None


def test_clean_odrzuca_nieznany_klucz():
    posted = json.dumps(
        [
            {"klucz": "nieistniejaca_sekcja", "widoczna": True, "limit": None},
            {"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None},
        ]
    )
    klucze = [p["klucz"] for p in _clean_uklad(posted)]
    assert "nieistniejaca_sekcja" not in klucze
    assert klucze == [KLUCZ_WYKRES_LATA]


def test_clean_koryguje_niedozwolony_limit():
    posted = json.dumps([{"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 7}])
    assert _clean_uklad(posted)[0]["limit"] == DOMYSLNY_LIMIT


def test_clean_pustej_wartosci_nie_wywala_i_dziala_z_rozwiaz_uklad():
    wartosc = _clean_uklad("")
    assert wartosc in (None, [])

    # rozwiaz_uklad musi tolerować pustą wartość (forward-compat z None)
    uczelnia = Uczelnia(uklad_profilu_autora=wartosc)
    sekcje = rozwiaz_uklad(uczelnia)
    assert sekcje  # domyślny układ → coś widać


@pytest.mark.django_db
def test_render_zawiera_kafelek_dla_kazdej_sekcji_katalogu():
    # render ładuje szablon przez dbtemplates.loader → potrzebny DB.
    widget = EdytorUkladuWidget()
    html = widget.render("uklad_profilu_autora", None)
    for typ in KATALOG_SEKCJI:
        assert typ.nazwa in html, f"brak kafelka dla {typ.klucz}"


@pytest.mark.django_db
def test_render_zaznacza_widoczne_sekcje_z_wartosci():
    wartosc = [
        {"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None},
        {"klucz": KLUCZ_STATYSTYKI_CHARAKTER, "widoczna": False, "limit": None},
    ]
    widget = EdytorUkladuWidget()
    html = widget.render("uklad_profilu_autora", wartosc)
    # checkbox dla widocznej sekcji ma "checked", dla ukrytej nie
    import re

    def _checkbox_checked(klucz):
        wzorzec = rf'<input type="checkbox"[^>]*data-klucz="{re.escape(klucz)}"([^>]*)>'
        m = re.search(wzorzec, html)
        assert m, f"brak checkboxa dla {klucz}"
        return "checked" in m.group(1)

    assert _checkbox_checked(KLUCZ_WYKRES_LATA) is True
    assert _checkbox_checked(KLUCZ_STATYSTYKI_CHARAKTER) is False


@pytest.mark.django_db
def test_render_limit_select_tylko_dla_sekcji_z_limitem():
    import re

    widget = EdytorUkladuWidget()
    html = widget.render("uklad_profilu_autora", None)

    def _ma_select(klucz):
        wzorzec = rf'<select[^>]*data-klucz="{re.escape(klucz)}"'
        return bool(re.search(wzorzec, html))

    # KLUCZ_NAJLEPSZE_PK ma_limit=True → select obecny
    assert _ma_select(KLUCZ_NAJLEPSZE_PK) is True
    # KLUCZ_WYKRES_LATA ma_limit=False → brak selecta
    assert _ma_select(KLUCZ_WYKRES_LATA) is False


@pytest.mark.django_db
def test_render_dolacza_sekcje_spoza_zapisanej_wartosci():
    # wartość zawiera tylko jedną sekcję — reszta katalogu i tak ma się pojawić
    wartosc = [{"klucz": KLUCZ_WYKRES_LATA, "widoczna": True, "limit": None}]
    widget = EdytorUkladuWidget()
    html = widget.render("uklad_profilu_autora", wartosc)
    for typ in KATALOG_SEKCJI:
        assert typ.nazwa in html


@pytest.mark.django_db
def test_round_trip_zapisuje_kanoniczny_schemat(uczelnia):
    # symulacja POST-a tego, co JS zserializował do ukrytego inputa
    posted = json.dumps(
        [
            {"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 50},
            {"klucz": KLUCZ_WYKRES_LATA, "widoczna": False, "limit": None},
        ]
    )
    wynik = _clean_uklad(posted)
    uczelnia.uklad_profilu_autora = wynik
    uczelnia.save()
    uczelnia.refresh_from_db()

    zapis = uczelnia.uklad_profilu_autora
    # każda pozycja ma DOKŁADNIE schemat {klucz, widoczna, limit}
    for poz in zapis:
        assert set(poz.keys()) == {"klucz", "widoczna", "limit"}
        assert isinstance(poz["widoczna"], bool)
    assert zapis[0] == {"klucz": KLUCZ_NAJLEPSZE_PK, "widoczna": True, "limit": 50}
    assert zapis[1] == {"klucz": KLUCZ_WYKRES_LATA, "widoczna": False, "limit": None}
    # i rozwiaz_uklad nadal działa na zapisanej wartości
    assert rozwiaz_uklad(uczelnia)


@pytest.mark.django_db
def test_edytor_renderuje_sie_na_stronie_zmiany_uczelni(admin_client, uczelnia):
    url = reverse("admin:bpp_uczelnia_change", args=(uczelnia.pk,))
    res = admin_client.get(url)
    assert res.status_code == 200
    tresc = res.content.decode("utf-8")
    # znana sekcja katalogu musi się pojawić w wyrenderowanym edytorze
    assert "Najczęstsi współautorzy" in tresc
    # hidden input z kanoniczną wartością
    assert 'name="uklad_profilu_autora"' in tresc
    # forma adminowa nie została ograniczona do jednego pola — inne pola
    # (np. nazwa, pbn_app_token) nadal się renderują
    assert 'name="nazwa"' in tresc
    assert 'name="pbn_app_token"' in tresc
