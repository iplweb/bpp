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

from unittest import mock

from django.urls import reverse


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
