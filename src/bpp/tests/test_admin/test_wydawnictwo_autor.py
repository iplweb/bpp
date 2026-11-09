"""Przycisk „Autorzy" (object-tools) na formularzu wydawnictwa w adminie.

Prowadzi do osobnej listy powiązań autorów rekordu
(``admin:bpp_<klasa>_autor_changelist?rekord__id__exact=<pk>``). Szablony
``admin/bpp/wydawnictwo_{ciagle,zwarte}/change_form.html`` renderują go tylko
dla istniejącego rekordu (``original.pk``) — przy dodawaniu go nie ma.
Pierwotnie (2021) etykieta brzmiała „Edycja autorów", później „Autorzy".

Na stronie dodawania link blokuje dodatkowo grappelli: jego
``admin/change_form.html`` renderuje blok ``object-tools`` tylko przy
``{% if change %}``. ``test_edit_btn_invisible`` pilnuje więc zamierzonego
zachowania niezależnie od tego, który szablon je zapewnia.
"""

import re

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.tests import normalize_html

KLASY = pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
    ],
)


def _przycisk_autorzy_re(klass):
    return re.compile(
        rf'<a href="{reverse(f"admin:bpp_{klass}_autor_changelist")}'
        r'\?rekord__id__exact=(\d+)">\s*Autorzy\s*</a>'
    )


@pytest.mark.django_db
@pytest.mark.parametrize("klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_changelist_no_argument(klass, admin_client):
    url = f"admin:bpp_{klass}_autor_changelist"
    res = admin_client.get(reverse(url))
    html = normalize_html(res.content.decode())
    assert "Musisz wejść w edycję" in html
    # Komunikat wskazuje faktyczną etykietę przycisku na formularzu rekordu.
    assert 'przycisk "Autorzy"' in html


@pytest.mark.django_db
@KLASY
def test_edit_btn_invisible(klass, model, admin_client):
    # Przy dodawaniu publikacji -- brak przycisku "Autorzy"
    res = admin_client.get(reverse(f"admin:bpp_{klass}_add"))
    assert res.status_code == 200

    html = normalize_html(res.content.decode())
    assert "?rekord__id__exact=" not in html
    assert not _przycisk_autorzy_re(klass).search(html)


@pytest.mark.django_db
@KLASY
def test_edit_btn_appears(klass, model, admin_client):
    # Przy edytowaniu publikacji -- przycisk "Autorzy" prowadzi do listy
    # autorów TEGO rekordu
    rekord = baker.make(model)
    baker.make(model)

    res = admin_client.get(reverse(f"admin:bpp_{klass}_change", args=(rekord.pk,)))
    assert res.status_code == 200

    znalezione = _przycisk_autorzy_re(klass).findall(
        normalize_html(res.content.decode())
    )
    assert znalezione == [str(rekord.pk)]
