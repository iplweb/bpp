"""Kontrakt DDL po fazie 02: widok filtruje, funkcja kasuje, bramka przepuszcza.

Odpowiednik ``test_views_sql.py`` (faza 01, ścieżka autorstwa) dla ścieżki
PUBLIKACJI. Podział ról jest ten sam: testy „substringowe"
(``pg_get_viewdef``/``pg_get_functiondef``/``pg_get_triggerdef``) pilnują
wyłącznie tego, że migracja ``0497`` w ogóle się odbyła, a wyrocznią
zachowania są testy SEMANTYCZNE na końcu pliku.

Najważniejszy z nich to ``test_publikacja_bez_zywych_autorow_ZOSTAJE``. Broni
przed „poprawką", która wygląda naturalnie i niszczy dane: dopisaniem
``deleted_at IS NULL`` tabeli ``*_autor`` do ``WHERE``/``ON`` widoku
rekordowego. Taki warunek degeneruje ``LEFT JOIN`` do ``INNER JOIN``, więc
publikacja, której WSZYSTKICH autorów soft-skasowano, wypada z
``bpp_rekord_mat`` — czyli znika z całego serwisu, mimo że sama nie została
skasowana. Testy substringowe tego NIE łapią: ``deleted_at`` jest w definicji
w obu wariantach.
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Jednostka, Praca_Doktorska, Wydawnictwo_Ciagle
from bpp.tests.test_soft_delete.test_kanarek_katalogowy import (
    _widoki_zalezne_od_deleted_at,
)

# (tabela publikacji, czy autor lezy na jej wierszu)
PUBLIKACJE = [
    ("bpp_wydawnictwo_ciagle", False),
    ("bpp_wydawnictwo_zwarte", False),
    ("bpp_patent", False),
    ("bpp_praca_doktorska", True),
    ("bpp_praca_habilitacyjna", True),
]

WIDOKI = [(t + "_view", t) for t, _ in PUBLIKACJE] + [
    (t + "_autorzy", t) for t, autor_na_wierszu in PUBLIKACJE if autor_na_wierszu
]

FUNKCJE = [
    ("bpp_refresh_rekord_wydawnictwo_ciagle", False),
    ("bpp_refresh_rekord_wydawnictwo_zwarte", False),
    ("bpp_refresh_rekord_patent", False),
    ("bpp_refresh_rekord_praca_doktorska", True),
    ("bpp_refresh_rekord_praca_habilitacyjna", True),
]

TRIGGERY = [(t, f"{t}_cache_upd") for t, _ in PUBLIKACJE]


# --- kontrakt DDL (dowód, że migracja się odbyła) -----------------------


@pytest.mark.django_db
@pytest.mark.parametrize("widok,tabela", WIDOKI)
def test_widok_zalezy_od_wlasnego_deleted_at(widok, tabela):
    """Widok musi zależeć od kolumny ``deleted_at`` WŁASNEJ tabeli.

    Pytamy ``pg_depend`` (przez helper kanarka katalogowego), a NIE tekst
    ``pg_get_viewdef``, z dwóch niezależnych powodów:

    1. Samo ``"deleted_at" in defn`` daje FAŁSZYWĄ ZIELEŃ: widoki rekordowe
       trzech typów z through-modelem zawierają ``count(...) FILTER (WHERE
       <tabela>_autor.deleted_at IS NULL)`` z migracji ``0494``, więc to
       słowo jest w nich obecne niezależnie od tej fazy.
    2. Dopisanie kwalifikacji (``<tabela>.deleted_at``) też nie działa:
       w widokach rodziny B (jedna tabela w zasięgu, bez JOIN-a) Postgres
       NORMALIZUJE predykat do gołego ``deleted_at IS NULL`` — kwalifikacja
       jest zbędna, więc ``pg_get_viewdef`` jej nie zwraca. Test tekstowy
       padałby mimo poprawnego filtra.

    Zależność kolumnowa w katalogu jest odporna na jedno i drugie.
    """
    with connection.cursor() as cur:
        zalezne = _widoki_zalezne_od_deleted_at(cur, [tabela])
    assert (widok, tabela) in zalezne, (
        f"{widok} nie zalezy od kolumny {tabela}.deleted_at — "
        f"filtr soft-delete nie zostal wpiety"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("fn,autor_na_wierszu", FUNKCJE)
def test_funkcja_refresh_ma_galaz_kasujaca(fn, autor_na_wierszu):
    """Bez DELETE odfiltrowanie z widoku jest no-opem (upsert nic nie usuwa)."""
    with connection.cursor() as cur:
        cur.execute("SELECT pg_get_functiondef(%s::regproc)", [fn])
        src = cur.fetchone()[0]
    assert "NEW.deleted_at IS NOT NULL" in src, f"{fn}: brak gałęzi kasującej"
    assert "DELETE FROM bpp_rekord_mat" in src, f"{fn}: brak DELETE z rekord_mat"
    if autor_na_wierszu:
        # Autor leży na wierszu publikacji, więc soft-delete publikacji musi
        # wyczyścić OBIE tabele _mat. Uwaga na różne nazwy klucza:
        # bpp_rekord_mat.id vs bpp_autorzy_mat.rekord_id.
        assert "DELETE FROM bpp_autorzy_mat" in src, (
            f"{fn}: autor na wierszu, a brak DELETE z autorzy_mat"
        )


@pytest.mark.django_db
@pytest.mark.parametrize("tabela,trigger", TRIGGERY)
def test_bramka_when_zna_deleted_at(tabela, trigger):
    """Bez deleted_at w bramce UPDATE soft-delete nie dochodzi do funkcji."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
            "WHERE t.tgrelid = %s::regclass AND t.tgname = %s",
            [tabela, trigger],
        )
        row = cur.fetchone()
    assert row is not None, f"brak triggera {trigger}"
    assert "deleted_at" in row[0], f"{trigger}: bramka WHEN nie zna deleted_at"


# --- testy semantyczne (wyrocznia zachowania) ---------------------------


def _ct(cur, model):
    cur.execute(
        "SELECT id FROM django_content_type WHERE app_label='bpp' AND model=%s",
        [model],
    )
    return cur.fetchone()[0]


def _jest_w_rekord_mat(cur, model, pk):
    cur.execute(
        "SELECT count(*) FROM bpp_rekord_mat WHERE id = ARRAY[%s, %s]::integer[]",
        [_ct(cur, model), pk],
    )
    return cur.fetchone()[0] > 0


def _liczba_w_autorzy_mat(cur, model, pk):
    cur.execute(
        "SELECT count(*) FROM bpp_autorzy_mat "
        "WHERE rekord_id = ARRAY[%s, %s]::integer[]",
        [_ct(cur, model), pk],
    )
    return cur.fetchone()[0]


@pytest.mark.django_db
def test_soft_delete_publikacji_znika_z_rekord_mat_restore_wraca():
    jednostka = baker.make(Jednostka)
    autor = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski")
    wc = baker.make(Wydawnictwo_Ciagle, szczegoly="sz", uwagi="u")
    wc.dodaj_autora(autor, jednostka)

    with connection.cursor() as cur:
        assert _jest_w_rekord_mat(cur, "wydawnictwo_ciagle", wc.pk), (
            "publikacja nie trafiła do bpp_rekord_mat jeszcze przed kasowaniem "
            "— setup testu jest zepsuty, nie sprawdzamy niczego"
        )

    wc.delete()

    with connection.cursor() as cur:
        assert not _jest_w_rekord_mat(cur, "wydawnictwo_ciagle", wc.pk), (
            "soft-skasowana publikacja została w bpp_rekord_mat"
        )
        assert _liczba_w_autorzy_mat(cur, "wydawnictwo_ciagle", wc.pk) == 0, (
            "autorstwa soft-skasowanej publikacji zostały w bpp_autorzy_mat"
        )

    wc.restore()

    with connection.cursor() as cur:
        assert _jest_w_rekord_mat(cur, "wydawnictwo_ciagle", wc.pk), (
            "po restore publikacja nie wróciła do bpp_rekord_mat"
        )
        assert _liczba_w_autorzy_mat(cur, "wydawnictwo_ciagle", wc.pk) == 1, (
            "po restore autorstwo nie wróciło do bpp_autorzy_mat"
        )


@pytest.mark.django_db
def test_publikacja_bez_zywych_autorow_ZOSTAJE():
    """REGRESJA na pułapkę agregatu — patrz docstring modułu.

    Publikacja, której WSZYSTKIE autorstwa są soft-skasowane, ma zostać w
    ``bpp_rekord_mat`` z ``liczba_autorow = 0``. Sama publikacja nie została
    skasowana, więc jej zniknięcie z serwisu byłoby utratą danych.
    """
    jednostka = baker.make(Jednostka)
    autor = baker.make("bpp.Autor", imiona="Jan", nazwisko="Jedyny")
    wc = baker.make(Wydawnictwo_Ciagle, szczegoly="sz", uwagi="u")
    wca = wc.dodaj_autora(autor, jednostka)

    wca.delete()  # kasujemy AUTORSTWO, nie publikację

    # WYROCZNIĄ JEST WIDOK, NIE CACHE. Wiersz w ``bpp_rekord_mat`` pochodzi
    # z chwili utworzenia publikacji, a soft-delete autorstwa odpala trigger
    # ścieżki autorstwa (``bpp_autorzy_mat``) — ``bpp_rekord_mat`` nie jest
    # wtedy przeliczany. Sprawdzanie samego cache'u przepuszczało zepsuty
    # widok: nieświeży wiersz maskował degenerację LEFT JOIN-a (potwierdzone
    # mutacyjnie przy pisaniu tego testu).
    with connection.cursor() as cur:
        cur.execute(
            "SELECT liczba_autorow FROM bpp_wydawnictwo_ciagle_view "
            "WHERE object_id_raw = %s",
            [wc.pk],
        )
        wiersz = cur.fetchone()
        assert wiersz is not None, (
            "publikacja bez żywych autorów WYPADŁA z bpp_wydawnictwo_ciagle_view "
            "— LEFT JOIN zdegenerował do INNER JOIN (utrata danych!)"
        )
        assert wiersz[0] == 0, f"liczba_autorow = {wiersz[0]}, oczekiwano 0"

    # Dopiero teraz cache: wymuszamy przeliczenie rekordu i sprawdzamy, że
    # projekcja widoku faktycznie do niego dociera.
    wc.save()

    with connection.cursor() as cur:
        assert _jest_w_rekord_mat(cur, "wydawnictwo_ciagle", wc.pk), (
            "publikacja bez żywych autorów WYPADŁA z bpp_rekord_mat po przeliczeniu"
        )
        cur.execute(
            "SELECT liczba_autorow FROM bpp_rekord_mat "
            "WHERE id = ARRAY[%s, %s]::integer[]",
            [_ct(cur, "wydawnictwo_ciagle"), wc.pk],
        )
        assert cur.fetchone()[0] == 0, "liczba_autorow w cache nie zeszła do zera"


@pytest.mark.django_db
def test_soft_delete_doktoratu_czysci_obie_tabele_mat():
    """Doktorat ma autora na WŁASNYM wierszu, więc jego soft-delete musi
    wyczyścić zarówno ``bpp_rekord_mat``, jak i ``bpp_autorzy_mat`` — to
    jedyne dwa modele, dla których gałąź kasująca dotyka obu tabel."""
    pd = baker.make(Praca_Doktorska, szczegoly="sz", uwagi="u")

    with connection.cursor() as cur:
        assert _jest_w_rekord_mat(cur, "praca_doktorska", pd.pk), (
            "doktorat nie trafił do bpp_rekord_mat — setup testu zepsuty"
        )
        assert _liczba_w_autorzy_mat(cur, "praca_doktorska", pd.pk) == 1, (
            "autor doktoratu nie trafił do bpp_autorzy_mat — setup zepsuty"
        )

    pd.delete()

    with connection.cursor() as cur:
        assert not _jest_w_rekord_mat(cur, "praca_doktorska", pd.pk), (
            "soft-skasowany doktorat został w bpp_rekord_mat"
        )
        assert _liczba_w_autorzy_mat(cur, "praca_doktorska", pd.pk) == 0, (
            "autor soft-skasowanego doktoratu został w bpp_autorzy_mat"
        )
