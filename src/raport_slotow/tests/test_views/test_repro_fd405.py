"""Repro dla FD#405 — eksport PDF raportu slotów-autora.

Objaw zgłoszony przez klienta (publikacje.up.lublin.pl): wygenerowany PDF
zawiera „chrome" strony WWW — górne menu, surowy szablon mustache
``{{#clickURL}}``, link „Przejdź do głównej zawartości" i stopkę serwisu —
zamiast samego raportu. Przyczyna: gałąź PDF renderowała pełny szablon
``base.html`` i podawała go WeasyPrintowi, licząc na ukrycie chrome przez
reguły ``@media print`` ze skompilowanego CSS, który na produkcji się nie
wczytuje.

Test przechwytuje HTML przekazywany do WeasyPrint (bez realnego renderowania
PDF) i sprawdza, że chrome NIE wycieka, a treść raportu jest obecna.
"""

import io
from unittest import mock

import pytest
from django.urls import reverse

from raport_slotow import const
from raport_slotow.views import SESSION_KEY


def _otworz_raport(admin_app, autor):
    url = reverse("raport_slotow:index")
    form_page = admin_app.get(url)

    autor_form = None
    for form in form_page.forms.values():
        if "obiekt" in form.fields:
            autor_form = form
            break
    assert autor_form is not None, "Form with 'obiekt' field not found"
    autor_form["obiekt"].force_value(autor.pk)
    return autor_form.submit().maybe_follow()


def test_repro_fd405_pdf_bez_chrome(admin_app, autor_jan_kowalski):
    raport_page = _otworz_raport(admin_app, autor_jan_kowalski)

    captured = {}

    class FakeHTML:
        def __init__(self, *args, string=None, **kwargs):
            captured["string"] = string

        def write_pdf(self, *args, **kwargs):
            return b"%PDF-1.7\nfake"

    with mock.patch("weasyprint.HTML", FakeHTML):
        pdf_page = raport_page.click("pobierz PDF")

    assert pdf_page.status_code == 200

    html = captured.get("string")
    assert html is not None, "WeasyPrint nie został wywołany z HTML-em"
    if isinstance(html, bytes):
        html = html.decode("utf-8")

    # chrome strony WWW NIE może trafiać do PDF:
    assert "{{#clickURL}}" not in html, "szablon mustache powiadomień wyciekł"
    assert "messageTemplate" not in html, "div #messageTemplate wyciekł"
    assert "Przejdź do głównej zawartości" not in html, "skip-link wyciekł do PDF"
    assert "iplweb" not in html, "stopka serwisu wyciekła do PDF"

    # treść raportu MUSI pozostać:
    assert "Raport slotów" in html
    assert str(autor_jan_kowalski) in html


def _captured_pdf_html(admin_client, autor, rok):
    """Ustawia sesję raportu i przechwytuje HTML podawany WeasyPrintowi."""
    dane_raportu = {
        "obiekt": autor.pk,
        "od_roku": rok,
        "do_roku": rok,
        "dzialanie": const.DZIALANIE_WSZYSTKO,
        "minimalny_pk": 0,
        "slot": None,
        "_export": "html",
    }
    s = admin_client.session
    s.update({SESSION_KEY: dane_raportu})
    s.save()

    captured = {}

    class FakeHTML:
        def __init__(self, *args, string=None, **kwargs):
            captured["string"] = string

        def write_pdf(self, *args, **kwargs):
            return b"%PDF-1.7\nfake"

    with mock.patch("weasyprint.HTML", FakeHTML):
        res = admin_client.get(reverse("raport_slotow:raport") + "?_export=pdf")
    assert res.status_code == 200

    html = captured.get("string")
    assert html is not None, "WeasyPrint nie został wywołany z HTML-em"
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    return html


@pytest.mark.django_db
def test_fd405_pdf_pokazuje_tytul_dyscypliny(
    admin_client, autor_jan_kowalski, rekord_slotu, dyscyplina1, rok
):
    """FD#405 follow-up: każda tabela (osobna dla każdej dyscypliny) musi mieć
    w wydruku nagłówek z nazwą dyscypliny — inaczej przy autorze z kilkoma
    dyscyplinami nie wiadomo, której tabela dotyczy."""
    html = _captured_pdf_html(admin_client, autor_jan_kowalski, rok)

    assert "Dyscyplina:" in html, "brak nagłówka z nazwą dyscypliny nad tabelą"
    assert str(dyscyplina1) in html


def _strony_ze_stopka(tfoot_css):
    """Renderuje krótką tabelę na celowo malutkiej stronie (żeby zajęła kilka
    podstron) i liczy, na ilu stronach pojawia się stopka <tfoot>."""
    from pypdf import PdfReader
    from weasyprint import HTML

    rows = "".join(f"<tr><td>wiersz {i}</td><td>1</td></tr>" for i in range(12))
    table = (
        "<table><thead><tr><th>Tytuł</th><th>Pkt</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "<tfoot><tr><td>SUMA</td><td>SUMA_9999</td></tr></tfoot></table>"
    )
    css = (
        "@page{size:5cm 5cm;margin:2mm} thead{display:table-header-group} "
        f"{tfoot_css} td,th{{border:.5pt solid #000;font-size:7pt}}"
    )
    pdf = HTML(
        string=f"<html><head><style>{css}</style></head><body>{table}</body></html>"
    ).write_pdf()
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 2, "tabela powinna zająć kilka podstron"
    return sum(
        1 for p in reader.pages if "SUMA_9999" in p.extract_text().replace(" ", "")
    )


def test_fd405_pdf_stopka_sumy_tylko_raz_na_wielu_stronach():
    """FD#405 follow-up: stopka tabeli z sumą (SummingColumn → <tfoot>) nie
    może się powtarzać na każdej podstronie. Domyślne `table-footer-group`
    powtarza ją na każdej stronie (bug); `table-row-group` pokazuje raz."""
    # kontrola negatywna — potwierdza, że test faktycznie rozróżnia zachowania
    assert _strony_ze_stopka("tfoot{display:table-footer-group}") >= 2
    # zachowanie użyte w szablonie PDF
    assert _strony_ze_stopka("tfoot{display:table-row-group}") == 1


def test_fd405_szablon_pdf_uzywa_table_row_group_dla_tfoot():
    """Strażnik: szablon PDF musi trzymać tfoot w `table-row-group`, żeby
    stopka z sumą nie powtarzała się na każdej stronie (FD#405)."""
    import pathlib

    import raport_slotow

    src = (
        pathlib.Path(raport_slotow.__file__).parent
        / "templates"
        / "raport_slotow"
        / "raport_slotow_autor_pdf.html"
    ).read_text(encoding="utf-8")
    assert "table-row-group" in src
