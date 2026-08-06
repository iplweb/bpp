"""WCAG 3.1.2 — atrybut ``lang`` na tytułach na stronach szczegółów.

Tytuł oryginalny bierze język z ``rekord.jezyk``. Tytuł PRZEŁOŻONY
(``tytul``) świadomie NIE dostaje atrybutu: model nie zawiera pola
opisującego jego język (``jezyk_alt`` to odwzorowanie atrybutu z API PBN
oznaczające drugi język PRACY, nie język przekładu). Bez atrybutu przekład
dziedziczy ``lang="pl"`` ze strony, co dla polskiego tłumaczenia jest
prawdą — a błędne oznaczenie byłoby gorsze niż brak.
"""

import pytest
from django.template.loader import render_to_string
from model_bakery import baker

from bpp.models.system import Jezyk

# Fixture ``jezyki`` (src/fixtures/conftest_system.py:65) tworzy słownik
# z WYPEŁNIONYM ``kod_bcp47``: polski → "pl", angielski → "en". Fixture
# ``wydawnictwo_ciagle`` już od niej zależy, więc wystarczy pobrać język
# po skrócie zamiast budować własny.


@pytest.fixture
def jezyk_angielski(jezyki):
    return Jezyk.objects.get(skrot="ang.")


@pytest.fixture
def jezyk_bez_kodu(db):
    return baker.make(Jezyk, nazwa="suahili", skrot="swa.", kod_bcp47="")


def _renderuj_mono(praca):
    return render_to_string(
        "browse/praca_tabela_mono.html",
        {"praca": praca, "autorzy": [], "rekord": praca, "links": "normal"},
    )


@pytest.mark.django_db
def test_mono_oznacza_tytul_oryginalny(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    tresc = _renderuj_mono(wydawnictwo_ciagle)

    assert 'lang="en"' in tresc


@pytest.mark.django_db
def test_mono_bez_atrybutu_gdy_kod_pusty(wydawnictwo_ciagle, jezyk_bez_kodu):
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł bez kodu"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_bez_kodu
    wydawnictwo_ciagle.save()

    tresc = _renderuj_mono(wydawnictwo_ciagle)

    assert "Tytuł bez kodu" in tresc
    assert 'lang=""' not in tresc


@pytest.mark.django_db
def test_mono_przeklad_zostaje_poza_znacznikiem(
    wydawnictwo_ciagle, jezyk_angielski
):
    # Znacznik obejmuje WYŁĄCZNIE tytuł oryginalny. Wspólny <span> na bloku
    # "oryginalny (przekład)" oznaczyłby jednym językiem dwa różne języki.
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X"
    wydawnictwo_ciagle.tytul = "Wpływ X"
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    tresc = _renderuj_mono(wydawnictwo_ciagle)

    assert '<span lang="en">Effects of X</span>' in tresc
    assert "Wpływ X" in tresc
    assert '<span lang="en">Effects of X (Wpływ X)' not in tresc


@pytest.mark.django_db
def test_breadcrumb_oznacza_tytul(client, wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    res = client.get(wydawnictwo_ciagle.get_absolute_url())

    assert res.status_code == 200
    assert b'lang="en"' in res.content


@pytest.mark.django_db
def test_breadcrumb_bez_atrybutu_gdy_kod_pusty(
    client, wydawnictwo_ciagle, jezyk_bez_kodu
):
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł bez kodu"
    wydawnictwo_ciagle.jezyk = jezyk_bez_kodu
    wydawnictwo_ciagle.save()

    res = client.get(wydawnictwo_ciagle.get_absolute_url())

    assert res.status_code == 200
    assert b'lang=""' not in res.content
