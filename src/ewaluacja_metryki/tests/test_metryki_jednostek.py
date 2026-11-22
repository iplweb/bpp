"""Metryki jednostki — zestawienie PDF dla kierownika (FD#617)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka, Uczelnia
from bpp.models.profile import BppUser
from ewaluacja_metryki import metryki_jednostek as r
from ewaluacja_metryki import metryki_jednostek_svg as svg
from ewaluacja_metryki.metryki_jednostek import zbuduj_metryki_jednostki
from ewaluacja_metryki.models import MetrykaAutora

from .conftest import wybierz_okres


def _metryka(jednostka, dyscyplina, okres, nazwisko, slot_max, slot, punkty):
    autor = baker.make(Autor, nazwisko=nazwisko, imiona="Jan")
    return MetrykaAutora.objects.create(
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        uczelnia=jednostka.uczelnia,
        okres=okres,
        slot_maksymalny=Decimal(slot_max),
        slot_nazbierany=Decimal(slot),
        punkty_nazbierane=Decimal(punkty),
        slot_wszystkie=Decimal(slot),
        punkty_wszystkie=Decimal(punkty),
        rodzaj_autora="N",
    )


@pytest.fixture
def klinika(db, okres_2022):
    uczelnia = baker.make(Uczelnia)
    jednostka = baker.make(Jednostka, nazwa="Klinika Testowa", uczelnia=uczelnia)
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.2")
    metryki = {
        # pełne sloty, średnia 100 (powyżej mediany) → filar
        "Filarowa": _metryka(jednostka, dyscyplina, okres_2022, "Filarowa", 4, 4, 400),
        # pełne sloty, średnia 40 (poniżej mediany) → ilość ponad jakość
        "Ilosciowa": _metryka(
            jednostka, dyscyplina, okres_2022, "Ilosciowa", 4, 4, 160
        ),
        # 1 z 4 slotów, średnia 140 → dobre prace, niewykorzystane sloty
        "Potencjalna": _metryka(
            jednostka, dyscyplina, okres_2022, "Potencjalna", 4, 1, 140
        ),
        # 1 z 4 slotów, średnia 20 → wymaga wsparcia
        "Wsparcie": _metryka(jednostka, dyscyplina, okres_2022, "Wsparcie", 4, 1, 20),
        # zero prac
        "Zerowa": _metryka(jednostka, dyscyplina, okres_2022, "Zerowa", 4, 0, 0),
    }
    # Metryka innej jednostki tej samej uczelni — nie może trafić do raportu
    inna = baker.make(Jednostka, nazwa="Inna Klinika", uczelnia=uczelnia)
    _metryka(inna, dyscyplina, okres_2022, "Obca", 4, 4, 800)
    return jednostka, dyscyplina, metryki


def _wiersz(raport, nazwisko):
    (grupa,) = raport.grupy
    return next(w for w in grupa.wiersze if w.autor.nazwisko == nazwisko)


@pytest.mark.django_db
def test_raport_przypisuje_cwiartki_i_statusy(klinika, okres_2022):
    jednostka, _, _ = klinika
    raport = zbuduj_metryki_jednostki(jednostka, jednostka.uczelnia, okres_2022)

    (grupa,) = raport.grupy
    assert {w.autor.nazwisko for w in grupa.wiersze} == {
        "Filarowa",
        "Ilosciowa",
        "Potencjalna",
        "Wsparcie",
        "Zerowa",
    }
    # mediana średnich osób z pracami: 20, 40, 100, 140 → 70
    assert grupa.mediana_sredniej == Decimal(70)

    assert _wiersz(raport, "Filarowa").kwadrant == r.KWADRANT_FILAR
    assert _wiersz(raport, "Ilosciowa").kwadrant == r.KWADRANT_ILOSC
    assert _wiersz(raport, "Potencjalna").kwadrant == r.KWADRANT_POTENCJAL
    assert _wiersz(raport, "Wsparcie").kwadrant == r.KWADRANT_WSPARCIE
    assert _wiersz(raport, "Zerowa").kwadrant == r.KWADRANT_BRAK

    assert _wiersz(raport, "Filarowa").status_wypelnienia == r.DOBRY
    assert _wiersz(raport, "Wsparcie").status_wypelnienia == r.SLABY
    assert _wiersz(raport, "Zerowa").status_wypelnienia == r.BRAK
    assert _wiersz(raport, "Potencjalna").status_jakosci == r.DOBRY
    assert _wiersz(raport, "Ilosciowa").status_jakosci == r.SLABY


@pytest.mark.django_db
def test_raport_liczy_sumy_i_potencjal(klinika, okres_2022):
    jednostka, _, _ = klinika
    (grupa,) = zbuduj_metryki_jednostki(jednostka, jednostka.uczelnia, okres_2022).grupy

    assert grupa.slot_maksymalny == Decimal(20)
    assert grupa.slot_nazbierany == Decimal(10)
    assert grupa.wypelnienie == Decimal(50)
    assert grupa.punkty == Decimal(720)
    # wolne sloty: 0 + 0 + 3 + 3 + 4 = 10, wartość slotu = mediana 70
    assert grupa.brakujace_sloty == Decimal(10)
    assert grupa.potencjal_punktow == Decimal(700)
    # potencjał zaczyna się od osoby z największą liczbą wolnych slotów
    assert grupa.wiersze_wg_potencjalu[0].autor.nazwisko == "Zerowa"
    # lista efektywności: od najwyższej średniej za slot
    assert [w.autor.nazwisko for w in grupa.wiersze_wg_sredniej][:2] == [
        "Potencjalna",
        "Filarowa",
    ]
    # średnia uczelni obejmuje też drugą jednostkę: (720 + 800) / (10 + 4)
    assert grupa.srednia_uczelni == Decimal(1520) / Decimal(14)
    assert any("wypełnia 50%" in w for w in grupa.wnioski)
    assert any("bez żadnej pracy" in w for w in grupa.wnioski)


@pytest.mark.django_db
def test_raport_pomija_inne_okresy(klinika, okres_2022, okres_2026):
    jednostka, _, _ = klinika
    assert zbuduj_metryki_jednostki(jednostka, jednostka.uczelnia, okres_2026).pusty


def _uzytkownik(client, **kwargs):
    user = baker.make(BppUser, **kwargs)
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_raport_wymaga_pelnych_uprawnien(client, klinika):
    jednostka, _, _ = klinika
    _uzytkownik(client)
    for url in (
        reverse("ewaluacja_metryki:metryki_jednostek"),
        reverse("ewaluacja_metryki:metryki_jednostki", args=[jednostka.pk]),
    ):
        assert client.get(url).status_code in (302, 403)


@pytest.mark.django_db
def test_raport_html_i_pdf(client, klinika, okres_2022):
    jednostka, _, _ = klinika
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    url = reverse("ewaluacja_metryki:metryki_jednostki", args=[jednostka.pk])

    html = client.get(url, {"format": "html"})
    assert html.status_code == 200
    tresc = html.content.decode()
    assert "Klinika Testowa" in tresc
    assert "Filarowa" in tresc
    assert "Obca" not in tresc
    assert "<svg" in tresc

    pdf = client.get(url)
    assert pdf.status_code == 200
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "metryki_jednostki_" in pdf["Content-Disposition"]


@pytest.mark.django_db
def test_raport_jednostki_bez_metryk_to_404(client, klinika, okres_2022):
    jednostka, _, _ = klinika
    pusta = baker.make(Jednostka, uczelnia=jednostka.uczelnia)
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    url = reverse("ewaluacja_metryki:metryki_jednostki", args=[pusta.pk])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_lista_jednostek_do_raportu(client, klinika, okres_2022):
    jednostka, _, _ = klinika
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    res = client.get(reverse("ewaluacja_metryki:metryki_jednostek"))
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "Klinika Testowa" in tresc
    assert reverse("ewaluacja_metryki:metryki_jednostki", args=[jednostka.pk]) in tresc


def test_pierscien_pelny_czesciowy_i_pusty():
    assert "<path" not in svg.pierscien(100, "#000", "100%")
    assert svg.pierscien(100, "#000", "100%").count("<circle") == 2
    assert "<path" in svg.pierscien(40, "#000", "40%")
    assert svg.pierscien(0, "#000", "0%").count("<circle") == 1


@pytest.mark.django_db
def test_wykres_babelkowy_escapuje_nazwiska(klinika, okres_2022):
    jednostka, _, metryki = klinika
    autor = metryki["Filarowa"].autor
    autor.nazwisko = "<script>x</script>"
    autor.save()
    (grupa,) = zbuduj_metryki_jednostki(jednostka, jednostka.uczelnia, okres_2022).grupy
    wykres = svg.wykres_babelkowy(grupa)
    assert "<script>" not in wykres
    assert "&lt;script&gt;" in wykres


def test_rozklad_punktacji_przedzialy_i_slabe_prace():
    przedzialy, slabe = r.rozklad_punktacji(
        [
            (Decimal(1), Decimal(200)),
            (Decimal(1), Decimal(140)),
            (Decimal("0.5"), Decimal(120)),  # 100–139
            (Decimal("0.5"), Decimal(70)),
            (Decimal(1), Decimal(40)),  # słaba (< 70)
            (Decimal(1), Decimal(20)),  # słaba
            (Decimal(1), None),  # brak punktacji → poniżej 40, słaba
        ]
    )
    assert [p.liczba_prac for p in przedzialy] == [1, 1, 1, 1, 1, 2]
    assert przedzialy[2].sloty == Decimal("0.5")
    assert sum(p.procent_slotow for p in przedzialy) == Decimal(100)
    # 3 z 6 slotów to prace poniżej 70 pkt
    assert slabe == Decimal(50)


def test_rozklad_punktacji_pusty():
    przedzialy, slabe = r.rozklad_punktacji([])
    assert slabe is None
    assert all(p.liczba_prac == 0 for p in przedzialy)


@pytest.mark.django_db
def test_struktura_punktacji_z_tabeli_cache(klinika, okres_2022):
    """Regresja: identyfikatory prac idą do zapytania jako listy — krotki
    wywracały raport na prawdziwych danych (``integer[] = integer``)."""
    from bpp.models import Cache_Punktacja_Autora, Wydawnictwo_Ciagle
    from bpp.models.cache import Rekord

    jednostka, dyscyplina, metryki = klinika
    metryka = metryki["Filarowa"]
    prace = []
    for punkty in (140, 40):
        wc = baker.make(Wydawnictwo_Ciagle, rok=2023, punkty_kbn=punkty)
        rekord_id = list(Rekord.objects.get_for_model(wc).pk)
        Cache_Punktacja_Autora.objects.create(
            rekord_id=rekord_id,
            autor=metryka.autor,
            jednostka=jednostka,
            dyscyplina=dyscyplina,
            pkdaut=punkty,
            slot=1,
        )
        prace.append(rekord_id)
    metryka.prace_nazbierane = prace
    metryka.save()

    (grupa,) = zbuduj_metryki_jednostki(jednostka, jednostka.uczelnia, okres_2022).grupy

    liczby = {p.etykieta: p.liczba_prac for p in grupa.struktura}
    assert liczby["140–199"] == 1
    assert liczby["40–69"] == 1
    assert grupa.procent_slotow_slabych_prac == Decimal(50)


@pytest.mark.django_db
def test_niezalogowany_trafia_na_logowanie(client, klinika):
    jednostka, _, _ = klinika
    for url in (
        reverse("ewaluacja_metryki:metryki_jednostek"),
        reverse("ewaluacja_metryki:metryki_jednostki", args=[jednostka.pk]),
    ):
        res = client.get(url)
        assert res.status_code == 302
        assert "login" in res["Location"]


# --- Dostęp: jednostki wskazane w profilu i kierownik jednostki -------------


def _url(jednostka):
    return reverse("ewaluacja_metryki:metryki_jednostki", args=[jednostka.pk])


@pytest.mark.django_db
def test_jednostki_wskazane_w_profilu(client, klinika, okres_2022):
    jednostka, _, _ = klinika
    inna = Jednostka.objects.get(nazwa="Inna Klinika")
    user = _uzytkownik(client)
    user.jednostki_metryk.add(jednostka)
    wybierz_okres(client, okres_2022)

    lista = client.get(reverse("ewaluacja_metryki:metryki_jednostek"))
    assert lista.status_code == 200
    tresc = lista.content.decode()
    assert "Klinika Testowa" in tresc
    assert "Inna Klinika" not in tresc

    assert client.get(_url(jednostka), {"format": "html"}).status_code == 200
    assert client.get(_url(inna), {"format": "html"}).status_code == 403


@pytest.mark.django_db
def test_wglad_obejmuje_podjednostki(client, klinika, okres_2022):
    jednostka, dyscyplina, _ = klinika
    poradnia = baker.make(
        Jednostka, nazwa="Poradnia", parent=jednostka, uczelnia=jednostka.uczelnia
    )
    _metryka(poradnia, dyscyplina, okres_2022, "Poradniana", 4, 4, 300)
    user = _uzytkownik(client)
    user.jednostki_metryk.add(jednostka)
    wybierz_okres(client, okres_2022)

    assert client.get(_url(poradnia), {"format": "html"}).status_code == 200


@pytest.mark.django_db
def test_bez_wgladu_403_a_nie_404(client, klinika, okres_2022):
    """Bez wglądu nie zdradzamy, czy jednostka w ogóle ma metryki."""
    jednostka, _, _ = klinika
    pusta = baker.make(Jednostka, uczelnia=jednostka.uczelnia)
    user = _uzytkownik(client)
    user.jednostki_metryk.add(jednostka)
    wybierz_okres(client, okres_2022)
    assert client.get(_url(pusta)).status_code == 403


def _kierownik(jednostka, **daty):
    from bpp.models import Autor_Jednostka, Funkcja_Autora

    funkcja, _ = Funkcja_Autora.objects.get_or_create(
        nazwa="kierownik", defaults={"skrot": "kier."}
    )
    autor = baker.make(Autor, nazwisko="Kierownicza", imiona="Anna")
    Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka, funkcja=funkcja, **daty
    )
    return autor


@pytest.mark.django_db
def test_kierownik_widzi_swoja_jednostke(client, klinika, okres_2022):
    jednostka, _, _ = klinika
    inna = Jednostka.objects.get(nazwa="Inna Klinika")
    user = _uzytkownik(client, autor=_kierownik(jednostka))
    wybierz_okres(client, okres_2022)

    assert client.get(_url(jednostka), {"format": "html"}).status_code == 200
    assert client.get(_url(inna), {"format": "html"}).status_code == 403

    profil = client.get(reverse("bpp:profil-uzytkownika"))
    tresc = profil.content.decode()
    assert "Metryki jednostek" in tresc
    assert _url(jednostka) in tresc
    assert _url(inna) not in tresc
    assert user.jednostki_metryk.count() == 0


@pytest.mark.django_db
def test_byly_kierownik_nie_ma_wgladu(client, klinika, okres_2022):
    import datetime

    jednostka, _, _ = klinika
    _uzytkownik(
        client,
        autor=_kierownik(jednostka, zakonczyl_prace=datetime.date(2020, 12, 31)),
    )
    wybierz_okres(client, okres_2022)

    assert client.get(_url(jednostka)).status_code == 403
    assert client.get(reverse("ewaluacja_metryki:metryki_jednostek")).status_code == 403
    assert (
        "Metryki jednostek"
        not in client.get(reverse("bpp:profil-uzytkownika")).content.decode()
    )


# --- Wyszukiwanie na liście jednostek ---------------------------------------


def test_do_wyszukiwania_bez_polskich_znakow():
    from ewaluacja_metryki.views.metryki_jednostek import do_wyszukiwania

    assert do_wyszukiwania("Klinika Łódzka ŻÓŁĆ") == "klinika lodzka zolc"


def test_filtruj_jednostki_wszystkie_slowa_dowolna_kolejnosc():
    from ewaluacja_metryki.views.metryki_jednostek import filtruj_jednostki

    wiersze = [
        {"jednostka_id": 1, "jednostka__nazwa": "II Klinika Ginekologii"},
        {"jednostka_id": 2, "jednostka__nazwa": "Klinika Pediatrii"},
        {
            "jednostka_id": 3,
            "jednostka__nazwa": "Zakład Biochemii",
            "jednostka__wydzial__nazwa": "Wydział Lekarski",
        },
    ]

    def ids(fraza):
        return [w["jednostka_id"] for w in filtruj_jednostki(wiersze, fraza)]

    assert ids("") == [1, 2, 3]
    assert ids("klinika") == [1, 2]
    assert ids("pediatrii klinika") == [2]
    assert ids("zaklad") == [3]  # bez polskich znaków
    assert ids("lekarski") == [3]  # po wydziale
    assert ids("onkologii") == []


@pytest.mark.django_db
def test_lista_jednostek_wyszukiwanie_q(client, klinika, okres_2022):
    jednostka, _, _ = klinika
    inna = Jednostka.objects.get(nazwa="Inna Klinika")
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)

    res = client.get(reverse("ewaluacja_metryki:metryki_jednostek"), {"q": "testowa"})
    assert res.status_code == 200
    assert res.context["liczba_pasujacych"] == 1
    pasuje = {w["jednostka_id"]: w["pasuje"] for w in res.context["jednostki"]}
    assert pasuje == {jednostka.pk: True, inna.pk: False}
    assert "Znaleziono 1 z 2" in res.content.decode()
