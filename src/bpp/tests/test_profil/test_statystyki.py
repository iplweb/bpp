"""Testy klikalnych statystyk wg charakteru → budowanie wyszukiwania."""

import json
from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from model_bakery import baker
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import Autor, Charakter_Formalny

pytestmark = pytest.mark.django_db


def test_statystyki_renderuja_formularz_po_charakterze():
    html = render_to_string(
        "browse/autor_sekcje/statystyki_charakter.html",
        {
            "nazwa": "Statystyki wg charakteru",
            "dane": {"wiersze": [("Artykuł", 5)], "suma": 5},
            "autor": SimpleNamespace(pk=7, __str__=lambda self: "Autor"),
        },
    )
    assert reverse("bpp:browse_build_search") in html
    assert 'name="charakter_formalny"' in html
    assert 'value="Artykuł"' in html
    # autor przekazany jako pk (NazwiskoIImieQueryObject rozwiązuje po pk)
    assert 'name="autor"' in html
    assert 'value="7"' in html


def test_build_search_buduje_box_dla_charakteru(client):
    autor = baker.make(Autor)
    baker.make(Charakter_Formalny, nazwa="Artykuł oryginalny")
    resp = client.post(
        reverse("bpp:browse_build_search"),
        {
            "autor": str(autor.pk),
            "charakter_formalny": "Artykuł oryginalny",
            "suggested-title": "x",
        },
    )
    assert resp.status_code == 302
    # Wartość sesji to JSON-string; parsujemy i szukamy pola charakteru.
    parsed = json.loads(client.session[MULTISEEK_SESSION_KEY])
    pola = [f for f in parsed["form_data"] if isinstance(f, dict)]
    charakter = [f for f in pola if f["field"] == "Charakter formalny"]
    assert charakter, "brak pola charakteru w zbudowanym formularzu"
    assert charakter[0]["value"] == "Artykuł oryginalny"


def test_charakter_value_to_web_pasuje_do_opcji_listy():
    """Klik w charakter → pole multiseeka pokazuje etykietę (nie pusto).

    Pole jest typu VALUE_LIST: zapisana wartość musi równać się jednej
    z opcji selecta (``values`` = etykiety MPTT z prefiksem/spacją). Bez
    ``value_to_web`` zapisana sama nazwa nie trafia w żadną opcję i pole jest
    puste — mimo że samo wyszukiwanie działa.
    """
    from bpp.multiseek_registry.fields.publication_type_fields import (
        CharakterFormalnyQueryObject,
    )

    baker.make(Charakter_Formalny, nazwa="Artykuł oryginalny")
    qo = CharakterFormalnyQueryObject()
    zmapowana = qo.value_to_web("Artykuł oryginalny")
    assert zmapowana in list(qo.values)
    # Idempotencja: zmapowanie gotowej etykiety daje tę samą etykietę.
    assert qo.value_to_web(zmapowana) == zmapowana
