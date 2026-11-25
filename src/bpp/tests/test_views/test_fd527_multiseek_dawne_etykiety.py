"""FD#527: wyszukiwarka a dawne etykiety pól w sesji użytkownika.

Multiseek rozpoznaje pola po etykiecie, a bieżący formularz trzyma w sesji —
migracja SQL jej nie dosięga (na produkcji sesje są w cache). Po zmianie
etykiet („Punkty MNiSW/MEiN” → „Punkty MNiSW”) użytkownik ze starą sesją
dostawał 500 na wynikach i na formularzu, bez wyjścia z interfejsu.
"""

import json
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from model_bakery import baker
from multiseek.logic import UnknownField
from multiseek.models import SearchForm
from multiseek.views import MULTISEEK_SESSION_KEY, MULTISEEK_SESSION_KEY_REMOVED

from bpp.models import Typ_KBN, Wydawnictwo_Ciagle
from bpp.multiseek_registry import registry
from bpp.multiseek_registry.dawne_etykiety import DAWNE_ETYKIETY, popraw_formularz
from bpp.views.mymultiseek import KOMUNIKAT_FORMULARZ_WYCZYSZCZONY

pytestmark = pytest.mark.django_db

STARE_PUNKTY = ["Punkty MNiSW/MEiN", "Punkty KBN", "Punkty PK"]
STARE_TYPY = ["Typ MNiSW/MEiN", "Typ KBN"]


def _formularz(etykieta, wartosc, operator=None):
    pole = registry.get_field_by_name(etykieta)
    return json.dumps(
        {
            "form_data": [
                None,
                {
                    "field": etykieta,
                    "operator": operator or str(pole.ops[0]),
                    "value": wartosc,
                    "prev_op": None,
                },
            ],
            "ordering": {"order_0": "6", "order_1": "8"},
            "report_type": "0",
        }
    )


def _ustaw_sesje(client, dane):
    sesja = client.session
    sesja[MULTISEEK_SESSION_KEY] = dane
    sesja.save()


@pytest.fixture
def praca(standard_data, denorms):
    typ = Typ_KBN.objects.get(skrot="PO")
    praca = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="FD527 sesja wyszukiwarki",
        punkty_kbn=Decimal("777"),
        typ_kbn=typ,
    )
    denorms.flush()
    return praca


def test_fd527_dawne_etykiety_wskazuja_istniejace_pola():
    obecne = {str(pole.label) for pole in registry.fields}
    assert set(STARE_PUNKTY + STARE_TYPY) <= set(DAWNE_ETYKIETY)
    for dawna, nowa in DAWNE_ETYKIETY.items():
        assert nowa in obecne
        assert registry.get_field_by_name(dawna) is registry.get_field_by_name(nowa)


def test_fd527_nieznane_pole_to_unknown_field():
    with pytest.raises(UnknownField):
        registry.get_field_by_name("Pole, którego nie ma")


@pytest.mark.parametrize("etykieta", [*STARE_PUNKTY, "Punkty MNiSW"])
def test_fd527_wyniki_ze_stara_etykieta_w_sesji(client, praca, etykieta):
    """Anonimowy użytkownik z dawną etykietą w sesji dostaje wyniki, nie 500."""
    _ustaw_sesje(client, _formularz(etykieta, 777))

    res = client.get(reverse("multiseek:results"))

    assert res.status_code == 200
    assert "FD527 sesja wyszukiwarki" in res.content.decode()
    # Sesja została przy okazji naprawiona — formularz ma już obecną etykietę.
    zapisane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    assert zapisane["form_data"][1]["field"] == "Punkty MNiSW"
    # Strażnik: reszta formularza (wartość, sortowanie) bez zmian.
    assert zapisane["form_data"][1]["value"] == 777
    assert zapisane["ordering"] == {"order_0": "6", "order_1": "8"}


@pytest.mark.parametrize("etykieta", [*STARE_TYPY, "Typ MNiSW"])
def test_fd527_formularz_ze_stara_etykieta_w_sesji(client, praca, etykieta):
    """Strona formularza odtwarza warunek pod OBECNĄ etykietą pola."""
    _ustaw_sesje(client, _formularz(etykieta, "Praca Oryginalna"))

    res = client.get(reverse("multiseek:index"))

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "multiseekFrame('addField', 'Typ MNiSW'" in tresc
    assert "MNiSW/MEiN" not in tresc
    assert "Typ KBN" not in tresc


def test_fd527_stara_etykieta_w_zagniezdzonej_grupie(client, praca):
    pole = registry.get_field_by_name("Punkty MNiSW")
    warunek = {
        "field": "Punkty MNiSW/MEiN",
        "operator": str(pole.ops[0]),
        "value": 777,
        "prev_op": None,
    }
    dane = json.dumps({"form_data": [None, [None, dict(warunek)], dict(warunek)]})
    poprawione = json.loads(popraw_formularz(dane))
    assert poprawione["form_data"][1][1]["field"] == "Punkty MNiSW"
    assert poprawione["form_data"][2]["field"] == "Punkty MNiSW"

    _ustaw_sesje(client, dane)
    assert client.get(reverse("multiseek:results")).status_code == 200


def test_fd527_post_ze_stara_etykieta(client, praca):
    """Formularz wysłany z karty otwartej przed zmianą etykiet."""
    res = client.post(
        reverse("multiseek:results"), {"json": _formularz("Punkty KBN", 777)}
    )
    assert res.status_code == 200
    assert "FD527 sesja wyszukiwarki" in res.content.decode()


def test_fd527_zapisany_formularz_ze_stara_etykieta(client, praca):
    """Zapisany formularz działa także bez migracji SQL (np. przywrócony
    z kopii albo zapisany między wdrożeniem a migracją)."""
    formularz = baker.make(
        SearchForm, public=True, data=_formularz("Typ MNiSW/MEiN", "Praca Oryginalna")
    )
    res = client.get(
        reverse("bpp-multiseek-load-form", args=(formularz.pk,)), follow=True
    )
    assert res.status_code == 200
    assert client.get(reverse("multiseek:results")).status_code == 200


@pytest.mark.parametrize("nazwa_url", ["multiseek:results", "multiseek:index"])
def test_fd527_nieznana_etykieta_czysci_formularz_zamiast_500(client, nazwa_url):
    dane = json.loads(_formularz("Punkty MNiSW", 1))
    dane["form_data"][1]["field"] = "Pole usunięte z wyszukiwarki"
    sesja = client.session
    sesja[MULTISEEK_SESSION_KEY] = json.dumps(dane)
    sesja[MULTISEEK_SESSION_KEY_REMOVED] = [1, 2]
    sesja.save()

    res = client.get(reverse(nazwa_url))

    assert res.status_code == 302
    assert res.url == reverse("multiseek:index")
    assert MULTISEEK_SESSION_KEY not in client.session
    assert MULTISEEK_SESSION_KEY_REMOVED not in client.session
    komunikaty = [str(m) for m in get_messages(res.wsgi_request)]
    assert komunikaty == [KOMUNIKAT_FORMULARZ_WYCZYSZCZONY]
    # Po przekierowaniu wyszukiwarka działa od zera.
    nastepna = client.get(res.url)
    assert nastepna.status_code == 200
    assert "nie udało się odtworzyć" in nastepna.content.decode()


def test_fd527_poprawny_formularz_w_sesji_nie_jest_ruszany(client, praca):
    """Strażnik: formularz z obecnymi etykietami zostaje w sesji bez zmian."""
    dane = _formularz("Punkty MNiSW", 777)
    _ustaw_sesje(client, dane)
    assert client.get(reverse("multiseek:results")).status_code == 200
    assert client.session[MULTISEEK_SESSION_KEY] == dane
    assert popraw_formularz(dane) is None
    assert popraw_formularz("to nie jest JSON") is None
    assert popraw_formularz(None) is None
