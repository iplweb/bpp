"""FD#446: zmiana etykiety kolumny w „Tabele” nie docierała do raportu.

Redaktor zmieniał etykietę kolumny (np. „Typ MNiSW/MEiN” na „Typ pracy”), a raport
— na ekranie i w eksportach — dalej pokazywał stary nagłówek, aż do restartu
serwera. Przyczyna leżała w ``django-flexible-reports`` < 0.4.0: klasa tabeli
była cache'owana per ``Table.pk`` na cały czas życia procesu.

Testy przechodzą przez prawdziwy widok raportu (ekran, XLSX, DOCX) i w obrębie
JEDNEGO procesu renderują raport przed zmianą etykiety i po niej — dokładnie
tak, jak robi to serwer aplikacji.
"""

import shutil
from io import BytesIO

import pytest
from django.urls import reverse
from flexible_reports.models import Column, ColumnOrder
from lxml import html as lxml_html
from model_bakery import baker

from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle
from nowe_raporty.seeding import definicje, seed_default_reports

STARA = "Typ MNiSW/MEiN"
NOWA = "Typ pracy"


@pytest.fixture
def url_raportu(db, uczelnia, typy_odpowiedzialnosci):
    seed_default_reports()
    # Pusta tabela nie renderuje nagłówków — raport musi mieć choć jedną pracę.
    jednostka = baker.make(Jednostka, skupia_pracownikow=True, uczelnia=uczelnia)
    autor = baker.make(Autor)
    praca = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Praca FD446", rok=2020
    )
    praca.dodaj_autora(autor, jednostka, zapisany_jako="Kowalski J.")
    return reverse(
        "nowe_raporty:raport_generuj", args=["raport-autorow", autor.pk, 2020, 2020]
    )


def _zmien_etykiete(stara, nowa):
    kolumna = Column.objects.get(parent__label=definicje.TABELA_LABEL, label=stara)
    kolumna.label = nowa
    kolumna.save()


def _naglowki_html(tekst):
    drzewo = lxml_html.fromstring(tekst)
    return {th.text_content().strip() for th in drzewo.iter("th")}


def _naglowki_ekran(client, url):
    res = client.get(url)
    assert res.status_code == 200
    return _naglowki_html(res.content.decode())


def _naglowki_xlsx(client, url):
    from openpyxl import load_workbook

    res = client.get(url + "?_export=xlsx")
    assert res.status_code == 200
    skoroszyt = load_workbook(BytesIO(res.content))
    naglowki = set()
    for arkusz in skoroszyt.worksheets:
        naglowki |= {komorka.value for komorka in arkusz[1]}
    return naglowki


def _naglowki_docx(client, url):
    from docx import Document

    res = client.get(url + "?_export=docx")
    assert res.status_code == 200
    dokument = Document(BytesIO(b"".join(res.streaming_content)))
    assert dokument.tables, "eksport DOCX nie zawiera żadnej tabeli"
    naglowki = set()
    for tabela in dokument.tables:
        naglowki |= {komorka.text.strip() for komorka in tabela.rows[0].cells}
    return naglowki


def test_fd446_zmiana_etykiety_widoczna_na_ekranie(admin_client, url_raportu):
    assert STARA in _naglowki_ekran(admin_client, url_raportu)

    _zmien_etykiete(STARA, NOWA)

    naglowki = _naglowki_ekran(admin_client, url_raportu)
    assert NOWA in naglowki
    assert STARA not in naglowki


def test_fd446_zmiana_etykiety_widoczna_w_xlsx(admin_client, url_raportu):
    assert STARA in _naglowki_xlsx(admin_client, url_raportu)

    _zmien_etykiete(STARA, NOWA)

    naglowki = _naglowki_xlsx(admin_client, url_raportu)
    assert NOWA in naglowki
    assert STARA not in naglowki


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="wymaga pandoc")
def test_fd446_zmiana_etykiety_widoczna_w_docx(admin_client, url_raportu):
    assert STARA in _naglowki_docx(admin_client, url_raportu)

    _zmien_etykiete(STARA, NOWA)

    naglowki = _naglowki_docx(admin_client, url_raportu)
    assert NOWA in naglowki
    assert STARA not in naglowki


def test_fd446_zmiana_etykiety_w_module_redagowania(admin_app, url_raportu):
    """Ta sama zmiana wykonana tak, jak robi to redaktor: „Tabele” → zapis."""
    assert STARA in _naglowki_html(admin_app.get(url_raportu).text)

    kolumna = Column.objects.get(parent__label=definicje.TABELA_LABEL, label=STARA)
    strona = admin_app.get(
        reverse("admin:flexible_reports_table_change", args=(kolumna.parent_id,))
    )
    formularz = next(
        f for f in strona.forms.values() if "column_set-0-label" in f.fields
    )
    pole = next(
        nazwa
        for nazwa, pola in formularz.fields.items()
        if nazwa
        and nazwa.startswith("column_set-")
        and nazwa.endswith("-label")
        and pola[0].value == STARA
    )
    formularz[pole] = NOWA
    formularz.submit(name="_save").maybe_follow()

    kolumna.refresh_from_db()
    assert kolumna.label == NOWA
    naglowki = _naglowki_html(admin_app.get(url_raportu).text)
    assert NOWA in naglowki
    assert STARA not in naglowki


# --- strażnicy: co ma się NIE zmienić ---------------------------------------


def test_fd446_pozostale_naglowki_bez_zmian(admin_client, url_raportu):
    przed = _naglowki_ekran(admin_client, url_raportu)

    _zmien_etykiete(STARA, NOWA)

    po = _naglowki_ekran(admin_client, url_raportu)
    assert po - {NOWA} == przed - {STARA}


def test_fd446_zmiana_etykiety_kolumny_sortujacej_nie_psuje_raportu(
    admin_client, url_raportu
):
    """„Rok” jest kolumną domyślnego sortowania tabeli — sortowanie wskazuje
    kolumnę, nie jej etykietę, więc po zmianie nazwy raport dalej się generuje
    (ekran i XLSX), a kolejność sortowania zostaje przy tej samej kolumnie."""
    _naglowki_ekran(admin_client, url_raportu)
    _zmien_etykiete("Rok", "Rok wydania")

    assert "Rok wydania" in _naglowki_ekran(admin_client, url_raportu)
    assert "Rok wydania" in _naglowki_xlsx(admin_client, url_raportu)
    sortowanie = ColumnOrder.objects.filter(
        table__label=definicje.TABELA_LABEL
    ).order_by("position")
    assert [s.column.label for s in sortowanie] == [
        "Rok wydania",
        "Opis bibliograficzny",
    ]


def test_fd446_kolumna_pominieta_w_eksporcie_zostaje_pominieta(
    admin_client, url_raportu
):
    """„Lp” ma włączone „Exclude from export” — zmiana etykiety tego nie rusza."""
    _zmien_etykiete("Lp", "Nr")

    assert "Nr" in _naglowki_ekran(admin_client, url_raportu)
    naglowki = _naglowki_xlsx(admin_client, url_raportu)
    assert "Nr" not in naglowki
    assert "Lp" not in naglowki
