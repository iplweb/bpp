"""FD#527: ``punkty_mnisw`` / ``typ_mnisw`` w kolumnach raportów.

Nowych nazw da się użyć w polu „Atrybut” kolumny tabeli raportu i w jej
szablonie — z wyświetlaniem, sortowaniem po kliknięciu w nagłówek i eksportem.
Dawne ``punkty_kbn`` / ``typ_kbn`` działają bez zmian (strażnicy).
"""

import re
from io import BytesIO
from urllib.parse import quote_plus

import pytest
from django.urls import reverse
from flexible_reports.models import Column
from model_bakery import baker

from bpp.models import Autor, Jednostka, Typ_KBN, Wydawnictwo_Ciagle
from nowe_raporty.seeding import definicje, seed_default_reports

PKT = "Pkt. MNiSW"
TYP = "Typ MNiSW"


@pytest.fixture
def url_raportu(db, uczelnia, typy_odpowiedzialnosci, denorms):
    seed_default_reports()
    jednostka = baker.make(Jednostka, skupia_pracownikow=True, uczelnia=uczelnia)
    autor = baker.make(Autor)
    # Tytuły i typy dobrane tak, żeby każde sortowanie dawało INNĄ kolejność
    # niż domyślna (rok, opis) — inaczej test przechodziłby bez sortowania.
    for tytul, punkty, skrot in (
        ("FD527 aaa", 140, "TB"),
        ("FD527 bbb", 20, "TC"),
        ("FD527 ccc", 70, "TA"),
    ):
        praca = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=tytul,
            rok=2020,
            punkty_kbn=punkty,
            impact_factor=1,
            typ_kbn=baker.make(Typ_KBN, nazwa=f"Typ {skrot}", skrot=skrot),
        )
        praca.dodaj_autora(autor, jednostka, zapisany_jako="Kowalski J.")
    denorms.flush()
    return reverse(
        "nowe_raporty:raport_generuj", args=["raport-autorow", autor.pk, 2020, 2020]
    )


def _kolumna(etykieta):
    return Column.objects.get(parent__label=definicje.TABELA_LABEL, label=etykieta)


def _ustaw(etykieta, **pola):
    kolumna = _kolumna(etykieta)
    for nazwa, wartosc in pola.items():
        setattr(kolumna, nazwa, wartosc)
    # ``full_clean`` = to samo, co sprawdza formularz w module redagowania.
    kolumna.full_clean()
    kolumna.save()


def _tytuly(client, url, sort=None):
    if sort:
        url += "?sort=" + quote_plus(sort)
    res = client.get(url)
    assert res.status_code == 200
    return re.findall(r"FD527 [abc]{3}", res.content.decode())


def _wiersze_xlsx(client, url):
    from openpyxl import load_workbook

    res = client.get(url + "?_export=xlsx")
    assert res.status_code == 200
    arkusz = load_workbook(BytesIO(res.content)).worksheets[0]
    naglowki = [komorka.value for komorka in arkusz[1]]
    return [
        dict(zip(naglowki, wiersz, strict=False))
        for wiersz in arkusz.iter_rows(min_row=2, values_only=True)
        if wiersz[naglowki.index(PKT)] is not None
    ]


@pytest.mark.parametrize(
    "atrybut_pkt,atrybut_typ",
    [
        # strażnik: dawne nazwy
        ("punkty_kbn", "typ_kbn"),
        ("punkty_mnisw", "typ_mnisw"),
        ("punkty_mnisw", "typ_mnisw.nazwa"),
    ],
)
def test_fd527_atrybut_kolumny_ekran_sortowanie_eksport(
    admin_client, url_raportu, atrybut_pkt, atrybut_typ
):
    _ustaw(PKT, attr_name=atrybut_pkt)
    _ustaw(TYP, attr_name=atrybut_typ)

    html = admin_client.get(url_raportu).content.decode()
    for wartosc in ("140,00", "20,00", "70,00", "Typ TA", "Typ TB", "Typ TC"):
        assert wartosc in html

    # sortowanie po kliknięciu w nagłówek — rosnąco i malejąco
    rosnaco = ["FD527 bbb", "FD527 ccc", "FD527 aaa"]
    assert _tytuly(admin_client, url_raportu, PKT) == rosnaco
    assert _tytuly(admin_client, url_raportu, "-" + PKT) == rosnaco[::-1]
    po_typie = _tytuly(admin_client, url_raportu, TYP)
    assert sorted(po_typie) == sorted(rosnaco)
    assert _tytuly(admin_client, url_raportu, "-" + TYP) == po_typie[::-1]

    wiersze = _wiersze_xlsx(admin_client, url_raportu)
    assert sorted(float(w[PKT]) for w in wiersze) == [20.0, 70.0, 140.0]
    assert sorted(w[TYP] for w in wiersze) == ["Typ TA", "Typ TB", "Typ TC"]


def test_fd527_sortowanie_po_typie_jak_po_starej_nazwie(admin_client, url_raportu):
    _ustaw(TYP, attr_name="typ_kbn")
    stare = _tytuly(admin_client, url_raportu, TYP)
    _ustaw(TYP, attr_name="typ_mnisw")
    assert _tytuly(admin_client, url_raportu, TYP) == stare


def test_fd527_szablon_kolumny_z_nowymi_nazwami(admin_client, url_raportu):
    _ustaw(
        TYP,
        attr_name="typ_mnisw",
        template="[{{ record.punkty_mnisw }}|{{ record.typ_mnisw }}"
        "|{{ record.typ_mnisw.nazwa }}|{{ record.typ_mnisw.skrot }}]",
    )
    html = admin_client.get(url_raportu).content.decode()
    assert "[140,00|Typ TB|Typ TB|TB]" in html
    assert "[20,00|Typ TC|Typ TC|TC]" in html

    # strażnik: ten sam szablon na dawnych nazwach daje to samo
    _ustaw(
        TYP,
        attr_name="typ_kbn",
        template="[{{ record.punkty_kbn }}|{{ record.typ_kbn }}"
        "|{{ record.typ_kbn.nazwa }}|{{ record.typ_kbn.skrot }}]",
    )
    html = admin_client.get(url_raportu).content.decode()
    assert "[140,00|Typ TB|Typ TB|TB]" in html


def test_fd527_atrybut_z_literowka_nadal_odrzucany(url_raportu):
    from django.core.exceptions import ValidationError

    for zly in ("punkty_mniswx", "typ_mnisw.nie_ma_takiego"):
        kolumna = _kolumna(PKT)
        kolumna.attr_name = zly
        with pytest.raises(ValidationError):
            kolumna.full_clean()
