"""Warunki wstepne soft-delete wobec triggerow cache (PR #312, faza 01/02).

Spec soft-delete (2026-06-04) zaklada dwa fakty o warstwie cache:

1. ``deleted_at`` ustawione UPDATE-em dolecialoby do triggera cache;
2. filtr ``deleted_at IS NULL`` w widoku zrodlowym WYSTARCZY, bo trigger na
   UPDATE robi bezwarunkowy DELETE z ``_mat`` przed upsertem ("inwariant,
   ktory MUSI przetrwac optymalizacje" -- plan 00).

Oba fakty przestaly obowiazywac po migracjach 0432 (port PL/pgSQL, upsert bez
DELETE) i 0433 (bramka WHEN na liscie kolumn z pg_depend). Poczatkowo (przed
faza 01) ponizsze dwa testy to PRZYPINALY -- byly ZIELONE na ówczesnym
kodzie, dokumentujac stan "soft-delete by nie zadzialal".

Faza 01 objela WYLACZNIE tabele ``*_Autor`` (migracja 0489: widok filtruje,
funkcja refresh ma galaz kasujaca, bramka WHEN zna ``deleted_at`` -- patrz
``test_soft_delete/test_views_sql.py``), a faza 02 -- 5 tabel PUBLIKACJI
(migracje 0496 i 0497, patrz ``test_soft_delete/test_views_sql_publikacje.py``).

Historia tego pliku, bo tlumaczy jego ksztalt:

- oryginalne dwa testy zostaly po fazie 01 ODWROCONE na docelowe asercje (to,
  co soft-delete MA robic) i oznaczone ``xfail(strict=True)``, bo dla
  publikacji mechanizmu jeszcze nie bylo. Zeby w ogole dalo sie je napisac,
  dokladaly kolumne ``deleted_at`` ALTER-em i owijaly widok filtrem WEWNATRZ
  transakcji testowej;
- faza 02 dostarczyla jedno i drugie NAPRAWDE, wiec symulacja zostala
  usunieta, a wraz z nia markery ``xfail``. Testy sa teraz zwyklymi testami
  regresyjnymi;
- ich ODPOWIEDNIKI dla ``bpp_wydawnictwo_ciagle_autor`` / ``bpp_autorzy_mat``
  (dopisane w fazie 01) zostaja -- pokrywaja druga sciezke.

Surowy SQL, zeby izolowac sam trigger bazodanowy (bez denorm / sygnalow
Django).
"""

import pytest
from django.db import connection

from bpp.tests.util import any_ciagle


def _ct(cur, model):
    cur.execute(
        "SELECT id FROM django_content_type WHERE app_label='bpp' AND model=%s",
        [model],
    )
    return cur.fetchone()[0]


def _ctid(cur, ct, pk):
    """Fizyczne polozenie krotki w bpp_rekord_mat; None gdy wiersza nie ma.

    ctid, nie xmin: w obrebie jednej transakcji testowej kazdy zapis ma to samo
    xid, wiec xmin sie nie rusza nawet przy przepisaniu wiersza.
    """
    cur.execute(
        "SELECT ctid::text FROM bpp_rekord_mat WHERE id = ARRAY[%s, %s]::integer[]",
        [ct, pk],
    )
    row = cur.fetchone()
    return row[0] if row else None


@pytest.mark.django_db
def test_update_samego_deleted_at_odpala_trigger():
    """Bramka WHEN zna deleted_at -> UPDATE soft-delete odpala trigger,
    ktory kasuje wiersz z bpp_rekord_mat (ctid znika).

    Odwrocenie ``test_update_samego_deleted_at_nie_odpala_triggera`` (nazwa
    i asercja sprzed fazy 01). Do fazy 02 test byl ``xfail(strict=True)``,
    a kolumne ``deleted_at`` dokladal ALTER-em w transakcji testowej --
    faza 01 dotknela wylacznie tabel ``*_Autor``. Faza 02 (migracje 0496
    i 0497) dodala kolumne i bramke NAPRAWDE, wiec symulacja zniknela,
    a marker ``xfail`` razem z nia.
    """
    wc = any_ciagle(tytul_oryginalny="Bramka a soft-delete")
    pk = wc.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")

        przed = _ctid(cur, ct, pk)
        assert przed is not None, "wiersz powinien byc w bpp_rekord_mat po INSERT"

        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET deleted_at = now() WHERE id = %s",
            [pk],
        )
        po = _ctid(cur, ct, pk)

    assert po is None, (
        "UPDATE samego deleted_at NIE usunal wiersza z bpp_rekord_mat "
        f"(ctid {przed} -> {po}) -- bramka WHEN nie zna deleted_at"
    )


@pytest.mark.django_db
def test_soft_delete_usuwa_wiersz_z_mat():
    """Goly ``UPDATE ... SET deleted_at`` usuwa wiersz z bpp_rekord_mat.

    Odwrocenie ``test_filtr_widoku_sam_nie_usuwa_wiersza_z_mat`` (nazwa i
    asercja sprzed fazy 01). Jak w tescie wyzej: do fazy 02 byl to
    ``xfail(strict=True)`` z symulacja (ALTER + owijka widoku); faza 02
    dostarczyla filtr i galaz kasujaca naprawde (migracja 0497).

    Filtr widoku jest aktywny juz przy tworzeniu rekordu, ale ``deleted_at``
    jest wtedy NULL, wiec wiersz normalnie wchodzi do bpp_rekord_mat.
    """
    wc = any_ciagle(tytul_oryginalny="Filtr widoku bez DELETE", rok=2020)
    pk = wc.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")

        assert _ctid(cur, ct, pk) is not None

        # soft-delete: wiersz wypada z widoku zrodlowego
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET deleted_at = now() WHERE id = %s",
            [pk],
        )

        po = _ctid(cur, ct, pk)

    assert po is None, (
        "wiersz zostal w bpp_rekord_mat po UPDATE ... SET deleted_at -- "
        f"funkcja refresh nie kasuje przed upsertem (ctid: {po})"
    )


def _ctid_autor(cur, ct, wca_pk):
    """Fizyczne polozenie krotki w bpp_autorzy_mat; None gdy wiersza nie ma.

    Klucz PK w bpp_autorzy_mat to ARRAY[ct, wca_pk], gdzie ``ct`` to content
    type modelu PUBLIKACJI (np. wydawnictwo_ciagle), a ``wca_pk`` to pk
    wiersza through (``*_Autor``), NIE pk publikacji ani autora -- patrz
    migracje 0432 (``_create_rekord_function``/``bpp_refresh_autor_*``) i
    0489 (``_funkcja_z_galezia_kasujaca``: ``DELETE ... WHERE id =
    ARRAY[ct, NEW.id]``).
    """
    cur.execute(
        "SELECT ctid::text FROM bpp_autorzy_mat WHERE id = ARRAY[%s, %s]::integer[]",
        [ct, wca_pk],
    )
    row = cur.fetchone()
    return row[0] if row else None


@pytest.mark.django_db
def test_update_samego_deleted_at_odpala_trigger_autor(wydawnictwo_ciagle_z_autorem):
    """Odpowiednik ``test_update_samego_deleted_at_odpala_trigger`` (wyzej,
    xfail) dla ``*_Autor`` -- TU juz dziala (faza 01, migracja 0489).

    W przeciwienstwie do ``bpp_wydawnictwo_ciagle``, bramka WHEN triggera
    ``bpp_wydawnictwo_ciagle_autor_cache_upd`` ZNA ``deleted_at`` (dopisana
    do widoku ``bpp_wydawnictwo_ciagle_autorzy`` w kroku 1 migracji 0489,
    wciagnieta do bramki w kroku 3 przez ``pg_depend``). Goly UPDATE samego
    ``deleted_at`` odpala trigger i usuwa wiersz z ``bpp_autorzy_mat``.

    Wyrocznia: gdyby bramka regenerowana w 0489 nie objela ``deleted_at``
    (np. ktos odwrocil krok 3 migracji), UPDATE ponizej w ogole nie
    dotarlby do funkcji triggera -- ``po`` zostaloby rowne ``przed``.
    """
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    pk = wca.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")

        przed = _ctid_autor(cur, ct, pk)
        assert przed is not None, "wiersz powinien byc w bpp_autorzy_mat po INSERT"

        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle_autor SET deleted_at = now() WHERE id = %s",
            [pk],
        )
        po = _ctid_autor(cur, ct, pk)

    assert po is None, (
        "UPDATE samego deleted_at NIE usunal wiersza z bpp_autorzy_mat "
        f"(ctid {przed} -> {po}) -- bramka WHEN nie zna deleted_at dla *_Autor"
    )


@pytest.mark.django_db
def test_soft_delete_autor_usuwa_wiersz_z_mat_mimo_reedycji(
    wydawnictwo_ciagle_z_autorem,
):
    """Odpowiednik ``test_soft_delete_usuwa_wiersz_z_mat`` (wyzej, xfail)
    dla ``*_Autor`` -- TU juz dziala (faza 01, migracja 0489).

    Rozszerzony o krok, ktorego oryginal (dla publikacji) nie mial szans
    wykonac: PO soft-delete wymuszamy PONOWNE odpalenie triggera zmiana
    INNEJ, bramkowanej kolumny (``kolejnosc``). Galaz kasujaca w funkcji
    ``bpp_refresh_autor_wydawnictwo_ciagle`` (0489) jest bezwarunkowa --
    ``IF NEW.deleted_at IS NOT NULL THEN DELETE ...; RETURN NULL; END IF;``
    -- wiec kazde kolejne odpalenie triggera na juz skasowanym wierszu
    tylko PONAWIA DELETE (no-op), nigdy nie dochodzi do upsertu.

    Wyrocznia: gdyby galaz kasujaca nie konczyla sie ``RETURN NULL`` (czyli
    leciala dalej do upsertu tak jak w mutancie sprzed 0489), drugi UPDATE
    ponizej przywrocilby wiersz do ``bpp_autorzy_mat`` -- to dokladnie
    "inwariant delete-first", ktorego brak dla publikacji dokumentuje
    xfail-owany test wyzej.
    """
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    pk = wca.pk

    with connection.cursor() as cur:
        ct = _ct(cur, "wydawnictwo_ciagle")
        assert _ctid_autor(cur, ct, pk) is not None

        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle_autor SET deleted_at = now() WHERE id = %s",
            [pk],
        )
        assert _ctid_autor(cur, ct, pk) is None, "goly UPDATE deleted_at nie skasowal"

        # Wymuszamy PONOWNE odpalenie triggera zmiana INNEJ, bramkowanej
        # kolumny -- deleted_at nadal NOT NULL.
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle_autor SET kolejnosc = kolejnosc + 100 "
            "WHERE id = %s",
            [pk],
        )

        cur.execute(
            "SELECT count(*) FROM bpp_wydawnictwo_ciagle_autorzy WHERE (id)[2] = %s",
            [pk],
        )
        w_widoku = cur.fetchone()[0]
        po = _ctid_autor(cur, ct, pk)

    assert w_widoku == 0, "widok zrodlowy nie powinien zwracac skasowanego wiersza"
    assert po is None, (
        "skasowany wiersz WROCIL do bpp_autorzy_mat po edycji innej kolumny "
        f"-- galaz kasujaca nie jest bezwarunkowa (ctid: {po})"
    )
