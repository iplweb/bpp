"""Bramki regresyjne na N+1 w adminie, wykryte pomiarem na kopii produkcji.

Niezmiennik jest wszędzie ten sam: **liczba zapytań nie może rosnąć z liczbą
wierszy**. Dlatego testy nie przybijają konkretnej liczby zapytań (taka
asercja pęka przy każdej niezwiązanej zmianie), tylko porównują ten sam
widok dla małego i większego zbioru danych.

Dlaczego akurat ``bpp_uczelnia``: ``Jednostka.__str__`` czyta
``self.uczelnia.uzywaj_wydzialow``, żeby zdecydować, czy dokleić nazwę
wydziału. Każde wyrenderowanie jednostki bez ``select_related`` to osobny
SELECT. Na produkcji ``bpp.uczelnia`` jest cache'owana przez CACHEOPS, więc
w produkcyjnej konfiguracji te zapytania nie idą do PostgreSQL, tylko
zamieniają się w round-tripy do Redisa — niewidoczne dla licznika zapytań
SQL, ale w pełni widoczne na zegarze. Tu, w testach, CACHEOPS nie ma reguł,
więc N+1 widać wprost i da się je przybić.
"""

import pytest
from django.contrib import admin as dj_admin
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.admin.filters import WydzialAutoraFilter
from bpp.models import Autor, Jednostka, Wydawca, Wydawnictwo_Zwarte
from bpp.models.rodzaj_jednostki import RodzajJednostki


def _zapytania_do(ctx, tabela):
    return sum(f'FROM "{tabela}"' in q["sql"] for q in ctx.captured_queries)


def _zapytania_o_uczelnie(ctx):
    return _zapytania_do(ctx, "bpp_uczelnia")


def _nie_skaluje(admin_client, url, tabela, zbuduj):
    """Zwróć ``(przy_malej, przy_duzej)`` liczby zapytań do ``tabela``.

    ``zbuduj(ile)`` ma dołożyć ``ile`` wierszy widocznych na changelistcie.
    """
    zbuduj(1)
    with CaptureQueriesContext(connection) as maly:
        assert admin_client.get(url).status_code == 200
    przy_malej = _zapytania_do(maly, tabela)

    zbuduj(5)
    with CaptureQueriesContext(connection) as duzy:
        assert admin_client.get(url).status_code == 200
    return przy_malej, _zapytania_do(duzy, tabela)


@pytest.mark.django_db
def test_changelist_autorow_nie_dociaga_uczelni_per_wiersz(
    admin_client, uczelnia, monkeypatch
):
    """Changelista autorów: SELECT-y po Uczelnia nie skalują się z wierszami.

    Regresja, którą to łapie: ``AutorAdmin.list_select_related`` deklarował
    dla kolumny ``aktualna_jednostka`` tylko samą jednostkę i jej wydział,
    bez ``aktualna_jednostka__uczelnia``. Zmierzone na kopii produkcji:
    50 zapytań po ``bpp_uczelnia`` na stronę 50 autorów.

    ``aktualna_jednostka`` jest kolumną OPCJONALNĄ (``list_display_allowed``),
    włączaną per użytkownik przez ``dynamic_admin_columns`` — w świeżej bazie
    nie jest widoczna, a ``get_list_select_related`` dokłada JOIN-y tylko dla
    kolumn AKTUALNIE widocznych. Dlatego test musi ją najpierw włączyć;
    inaczej przechodziłby pusto i niczego nie pilnował.
    """
    url = reverse("admin:bpp_autor_changelist")
    autor_admin = dj_admin.site._registry[Autor]

    assert "aktualna_jednostka" in autor_admin.list_display_allowed, (
        "kolumna 'aktualna_jednostka' zniknęła z AutorAdmin — ten test pilnuje "
        "właśnie jej JOIN-a, więc trzeba go zaktualizować albo usunąć"
    )

    # Symuluj użytkownika, który tę kolumnę sobie włączył.
    widoczne = list(autor_admin.list_display_always) + ["aktualna_jednostka"]
    monkeypatch.setattr(
        type(autor_admin), "get_list_display", lambda self, request: widoczne
    )
    assert "aktualna_jednostka__uczelnia" in autor_admin.get_list_select_related(
        RequestFactory().get(url)
    ), "JOIN po uczelni nie wchodzi mimo widocznej kolumny — poprawka nie działa"

    def zbuduj(ile):
        for _ in range(ile):
            # uczelnia= jawnie: baker.make(Jednostka) bez tego tworzy WŁASNĄ
            # uczelnię, co zaburzyłoby liczenie.
            jednostka = baker.make(Jednostka, uczelnia=uczelnia)
            baker.make(Autor, aktualna_jednostka=jednostka)

    zbuduj(1)
    with CaptureQueriesContext(connection) as maly:
        assert admin_client.get(url).status_code == 200
    przy_jednym = _zapytania_o_uczelnie(maly)

    zbuduj(5)
    with CaptureQueriesContext(connection) as duzy:
        assert admin_client.get(url).status_code == 200
    przy_szesciu = _zapytania_o_uczelnie(duzy)

    assert przy_szesciu == przy_jednym, (
        f"liczba zapytań o Uczelnia rośnie z liczbą wierszy "
        f"({przy_jednym} → {przy_szesciu}) — wrócił N+1; sprawdź, czy "
        f"AutorAdmin.list_select_related nadal ciągnie "
        f"'aktualna_jednostka__uczelnia'"
    )


@pytest.mark.django_db
def test_filtr_wydzialu_nie_dociaga_uczelni_per_pozycja(admin_user, uczelnia):
    """``WydzialAutoraFilter.lookups`` buduje listę przez ``str(j)``.

    Bez ``select_related("uczelnia")`` każda pozycja listy rozwijanej to
    osobny SELECT po ``bpp_uczelnia``.
    """
    zadanie = RequestFactory().get("/admin/bpp/autor/")
    zadanie.user = admin_user

    def policz():
        filtr = WydzialAutoraFilter(zadanie, {}, Autor, dj_admin.site._registry[Autor])
        with CaptureQueriesContext(connection) as ctx:
            pozycje = filtr.lookups(zadanie, None)
        return _zapytania_o_uczelnie(ctx), len(pozycje)

    baker.make(Jednostka, uczelnia=uczelnia, parent=None, widoczna=True)
    przy_jednym, ile_jeden = policz()

    for _ in range(4):
        baker.make(Jednostka, uczelnia=uczelnia, parent=None, widoczna=True)
    przy_pieciu, ile_piec = policz()

    assert ile_piec > ile_jeden, "test nie ma czego mierzyć — lista się nie wydłużyła"
    assert przy_pieciu == przy_jednym, (
        f"liczba zapytań o Uczelnia rośnie z długością listy filtra "
        f"({przy_jednym} → {przy_pieciu}) — wrócił N+1 w "
        f"WydzialAutoraFilter.lookups"
    )


@pytest.mark.django_db
def test_changelist_jednostek_nie_dociaga_rodzaju_per_wiersz(admin_client, uczelnia):
    """Changelista jednostek: ``rodzaj`` musi wejść JOIN-em.

    ``ChangeList.get_queryset`` aplikuje ``list_select_related`` tylko wtedy,
    gdy queryset bazowy nie ma JESZCZE żadnego ``select_related`` — a
    ``JednostkaManager`` dokłada ``select_related("wydzial")``, więc cała
    deklaracja przepadała i ``rodzaj`` dociągał się per wiersz.
    Zmierzone na kopii produkcji: 51 zapytań po ``bpp_rodzajjednostki``.
    """
    url = reverse("admin:bpp_jednostka_changelist")

    def zbuduj(ile):
        for _ in range(ile):
            baker.make(
                Jednostka, uczelnia=uczelnia, rodzaj=baker.make(RodzajJednostki)
            )

    maly, duzy = _nie_skaluje(admin_client, url, "bpp_rodzajjednostki", zbuduj)
    assert duzy == maly, (
        f"zapytania o RodzajJednostki rosną z liczbą wierszy ({maly} → {duzy}) "
        f"— wrócił N+1; sprawdź JednostkaAdmin.get_queryset"
    )


@pytest.mark.django_db
def test_changelist_wyd_zwartych_nie_dociaga_wydawcy_per_wiersz(
    admin_client, uczelnia, monkeypatch
):
    """Kolumna ``wydawnictwo`` czyta ``self.wydawca.nazwa`` przez property.

    ``list_select_related`` mapowało wydawcę wyłącznie na jawną kolumnę
    ``wydawca``, więc przy domyślnym zestawie kolumn JOIN nie wchodził.
    Zmierzone na kopii produkcji: 35 zapytań po ``bpp_wydawca``.
    """
    url = reverse("admin:bpp_wydawnictwo_zwarte_changelist")
    adm = dj_admin.site._registry[Wydawnictwo_Zwarte]

    widoczne = list(adm.list_display_always) + ["wydawnictwo"]
    monkeypatch.setattr(type(adm), "get_list_display", lambda self, request: widoczne)

    def zbuduj(ile):
        for _ in range(ile):
            baker.make(Wydawnictwo_Zwarte, wydawca=baker.make(Wydawca))

    maly, duzy = _nie_skaluje(admin_client, url, "bpp_wydawca", zbuduj)
    assert duzy == maly, (
        f"zapytania o Wydawca rosną z liczbą wierszy ({maly} → {duzy}) — "
        f"wrócił N+1; sprawdź wpis 'wydawnictwo' w list_select_related"
    )
