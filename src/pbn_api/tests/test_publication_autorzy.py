"""Testy property ``Publication.autorzy``.

PBN przechowuje kolekcje autorów/redaktorów niespójnie: raz jako *dict*
kluczowany PBN UID-em autora (``{"<uid>": {"lastName": ..., "name": ...}}``),
a raz jako *listę* słowników. Szablon rekordu (``praca_tabela_mono.html``)
iterował po tej kolekcji zakładając listę słowników — przy dict-cie
``{% for autor in lista %}`` zwracał gołe klucze (UID-y, stringi), przez co
``autor.givenNames`` jako argument filtra ``default`` wysadzał stronę
(``VariableDoesNotExist``). Te testy pilnują, że ``autorzy`` zwraca zawsze
listę znormalizowanych słowników z polami ``lastName``/``firstName``.
"""

import pytest
from model_bakery import baker

from pbn_api.models import Publication


def _publikacja(object_dict):
    return baker.make(
        Publication,
        versions=[{"current": True, "object": object_dict}],
    )


@pytest.mark.django_db
def test_autorzy_dict_kluczowany_uidem_normalizuje_do_listy_slownikow():
    """Regresja: kształt z produkcji (rekord 3,306) — dict UID→dane."""
    pub = _publikacja(
        {
            "authors": {
                "5e709321878c28a0473a33f9": {
                    "lastName": "Windyga",
                    "name": "Jerzy",
                }
            }
        }
    )
    autorzy = pub.autorzy["authors"]
    assert isinstance(autorzy, list)
    assert autorzy[0]["lastName"] == "Windyga"
    assert autorzy[0]["firstName"] == "Jerzy"


@pytest.mark.django_db
def test_autorzy_lista_slownikow_z_givenNames():
    pub = _publikacja({"authors": [{"lastName": "Kowalski", "givenNames": "Jan"}]})
    autorzy = pub.autorzy["authors"]
    assert autorzy[0]["lastName"] == "Kowalski"
    assert autorzy[0]["firstName"] == "Jan"


@pytest.mark.django_db
def test_autorzy_lista_slownikow_z_firstName():
    pub = _publikacja({"editors": [{"lastName": "Nowak", "firstName": "Anna"}]})
    assert pub.autorzy["editors"][0]["firstName"] == "Anna"


@pytest.mark.django_db
def test_policz_autorow_dziala_dla_dict_kluczowanego_uidem():
    pub = _publikacja(
        {
            "authors": {"uid1": {"lastName": "A", "name": "B"}},
            "editors": {"uid2": {"lastName": "C", "name": "D"}},
        }
    )
    assert pub.policz_autorow() == 2


@pytest.mark.django_db
def test_autorzy_goly_uid_bez_danych_osobowych_nie_wybucha():
    """Defensywnie: gdyby PBN podał listę samych UID-ów (stringów),
    nie wysadzamy się — zwracamy puste pola zamiast crashować szablon."""
    pub = _publikacja({"authors": ["5e709321878c28a0473a33f9"]})
    autorzy = pub.autorzy["authors"]
    assert autorzy[0]["lastName"] == ""
    assert autorzy[0]["firstName"] == ""


@pytest.mark.django_db
def test_szablon_rekordu_nie_wybucha_na_dict_kluczowanym_uidem():
    """End-to-end odwzorowanie pętli z praca_tabela_mono.html."""
    from django.template import Context, Template

    pub = _publikacja({"authors": {"5e70": {"lastName": "Windyga", "name": "Jerzy"}}})
    tmpl = Template(
        "{% for typ, lista in pub.autorzy.items %}"
        "{% for autor in lista %}"
        "{{ autor.lastName }} {{ autor.firstName }}"
        "{% if not forloop.last %}, {% endif %}"
        "{% endfor %}{% endfor %}"
    )
    out = tmpl.render(Context({"pub": pub}))
    assert "Windyga" in out
    assert "Jerzy" in out
