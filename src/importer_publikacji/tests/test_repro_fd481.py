"""Freshdesk #481 — ostrzeżenie o dyscyplinach HST ma być żółte, nie czerwone.

Komunikat „Autorzy z dyscyplin HST … Zweryfikuj wartość." na kroku punktacji
to ostrzeżenie (``callout warning``), a nie błąd (``callout alert``). Błędy
formularza dalej renderują się jako ``callout alert``.
"""

import re
from types import SimpleNamespace

from django.template.loader import render_to_string

from importer_publikacji.forms import PunktacjaForm

TEMPLATE = "importer_publikacji/partials/step_punktacja.html"


def _render(ostrzezenie_hst, form=None):
    return render_to_string(
        TEMPLATE,
        {
            "session": SimpleNamespace(
                pk=1, jest_wydawnictwem_zwartym=False, zrodlo=None
            ),
            "form": form or PunktacjaForm(),
            "sugestia": SimpleNamespace(
                punkty=None, podstawa="", powod_braku="brak danych"
            ),
            "punktacja_zrodla": None,
            "poziom_wydawcy": None,
            "rok": 2024,
            "ostrzezenie_hst": ostrzezenie_hst,
        },
    )


def _callout_z_tekstem(html, tekst):
    for match in re.finditer(
        r'<div class="(callout[^"]*)">(.*?)</div>', html, flags=re.DOTALL
    ):
        if tekst in match.group(2):
            return match.group(1)
    return None


def test_repro_fd481_ostrzezenie_hst_jest_warning():
    html = _render(ostrzezenie_hst=True)

    assert _callout_z_tekstem(html, "Autorzy z dyscyplin HST") == "callout warning"


def test_repro_fd481_bez_hst_brak_ostrzezenia():
    html = _render(ostrzezenie_hst=False)

    assert "Autorzy z dyscyplin HST" not in html


def test_repro_fd481_bledy_formularza_nadal_alert():
    form = PunktacjaForm(data={"punkty_kbn": "nie-liczba"})
    assert not form.is_valid()

    html = _render(ostrzezenie_hst=True, form=form)

    assert '<div class="callout alert">' in html
