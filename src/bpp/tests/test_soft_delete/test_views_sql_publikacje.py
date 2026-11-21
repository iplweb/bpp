"""Kontrakt DDL soft-delete publikacji: widok filtruje, funkcja kasuje,
bramka przepuszcza (migracje ``0511`` i ``0512``).

Testy „substringowe" (``pg_get_functiondef``/``pg_get_triggerdef``) pilnują,
że migracje się odbyły; wyrocznią zachowania są testy SEMANTYCZNE na końcu
pliku (``bpp_rekord_mat``/``bpp_autorzy_mat`` po delete/restore).
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

    W widokach z jedną tabelą w zasięgu Postgres normalizuje predykat do
    gołego ``deleted_at IS NULL``, więc test tekstowy byłby kruchy.

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
    # Soft-delete publikacji czyści OBIE tabele _mat — także dla typów
    # z through-modelem (0512): *_autor nie ma własnego kosza.
    assert "DELETE FROM bpp_autorzy_mat" in src, f"{fn}: brak DELETE z autorzy_mat"
    if not autor_na_wierszu:
        assert "OLD.deleted_at IS NOT NULL" in src, f"{fn}: brak gałęzi restore"


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
def test_edycja_autorstwa_publikacji_z_kosza_nie_wraca_do_autorzy_mat():
    """Trigger tabeli ``*_autor`` upsertuje z widoku ``*_autorzy`` — a ten
    (``0512``) odcina autorstwa publikacji z kosza. Zapis takiego autorstwa
    (np. przez ``all_objects``) nie może go wskrzesić w cache."""
    from bpp.models import Wydawnictwo_Ciagle_Autor

    jednostka = baker.make(Jednostka)
    autor = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski")
    wc = baker.make(Wydawnictwo_Ciagle, szczegoly="sz", uwagi="u")
    wca = wc.dodaj_autora(autor, jednostka)

    wc.delete()
    wca = Wydawnictwo_Ciagle_Autor.all_objects.get(pk=wca.pk)
    wca.zapisany_jako = "J. Kowalski (zmiana)"
    wca.save()

    with connection.cursor() as cur:
        assert _liczba_w_autorzy_mat(cur, "wydawnictwo_ciagle", wc.pk) == 0


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
