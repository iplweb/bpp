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
``test_soft_delete/test_views_sql.py``). Tabele publikacji (np.
``bpp_wydawnictwo_ciagle``) sa poza zakresem -- to faza 02. Dlatego:

- oryginalne dwa testy ponizej sa ODWROCONE na docelowe asercje (to co
  soft-delete MA robic), ale zostawione jako ``xfail`` -- to JEDYNY
  regresyjny dowod, ze bramka i galaz kasujaca dzialaja poprawnie DOPIERO
  po fazie 02 (gdy przestana byc xfail, to znak, ze ktos wdrozyl mechanizm
  dla publikacji i NIE zaktualizowal tego markera -- patrz uwaga przy
  ``xfail`` nizej);
- ponizej dopisane sa ich ODPOWIEDNIKI dla ``bpp_wydawnictwo_ciagle_autor``
  / ``bpp_autorzy_mat``, ktore juz DZIALAJA (faza 01) -- to one sa realnym
  dowodem regresyjnym na CO DZIEN, nie oryginaly.

Surowy SQL, zeby izolowac sam trigger bazodanowy (bez denorm / sygnalow
Django). Dla oryginalnych (publikacja) testow kolumne ``deleted_at``
dokladamy ALTER-em wewnatrz transakcji testowej -- DDL w Postgresie jest
transakcyjny, wiec rollback ja sprzata. Dla nowych (``*_Autor``) testow
ALTER nie jest potrzebny -- kolumna jest realna od migracji 0488.
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


def _dodaj_deleted_at(cur):
    cur.execute("ALTER TABLE bpp_wydawnictwo_ciagle ADD COLUMN deleted_at timestamptz")


def _filtruj_widok_po_deleted_at(cur):
    """Owija bpp_wydawnictwo_ciagle_view filtrem deleted_at IS NULL.

    Odpowiednik "mechanizmu #1" ze specu, bez ruszania oryginalnej definicji
    (CREATE OR REPLACE zachowuje liste kolumn -- bpp_rekord, ktory ten widok
    UNION-uje, pozostaje wazny).
    """
    cur.execute("SELECT pg_get_viewdef('bpp_wydawnictwo_ciagle_view'::regclass, true)")
    orig = cur.fetchone()[0].rstrip().rstrip(";")
    cur.execute(
        f"CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_view AS "
        f"SELECT * FROM ({orig}) _orig "
        f"WHERE _orig.object_id_raw NOT IN ("
        f"    SELECT id FROM bpp_wydawnictwo_ciagle WHERE deleted_at IS NOT NULL)"
    )


@pytest.mark.xfail(
    reason="faza 02 -- soft-delete publikacji (bpp_wydawnictwo_ciagle)",
    strict=True,
)
@pytest.mark.django_db
def test_update_samego_deleted_at_odpala_trigger():
    """Docelowo: bramka WHEN MA znac deleted_at -> UPDATE soft-delete MA
    odpalac trigger, ktory kasuje wiersz z bpp_rekord_mat (ctid znika).

    Odwrocenie ``test_update_samego_deleted_at_nie_odpala_triggera`` (nazwa
    i asercja sprzed fazy 01). Dla ``bpp_wydawnictwo_ciagle`` samej to
    dalej NIE dziala -- faza 01 dotknela wylacznie tabel ``*_Autor``
    (migracja 0489). Ten test ma pozostac xfail az do fazy 02; gdy
    zazieleni sie SAM (bez zmiany kodu tego pliku), oznacza to niezamierzona
    regresje zakresu -- zbadaj, co dotknelo bramki ``bpp_wydawnictwo_ciagle``.
    """
    # DDL PRZED utworzeniem rekordu: ALTER TABLE nie przejdzie, gdy tabela ma
    # zakolejkowane zdarzenia wyzwalaczy z INSERT-a w tej samej transakcji.
    with connection.cursor() as cur:
        _dodaj_deleted_at(cur)

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


@pytest.mark.xfail(
    reason="faza 02 -- soft-delete publikacji (bpp_wydawnictwo_ciagle)",
    strict=True,
)
@pytest.mark.django_db
def test_soft_delete_usuwa_wiersz_z_mat():
    """Docelowo: goly UPDATE ... SET deleted_at MA usunac wiersz z
    bpp_rekord_mat (mechanizm #1 -- filtr widoku -- wystarcza, bo funkcja
    refresh ma galaz kasujaca uruchamiana PRZED upsertem).

    Odwrocenie ``test_filtr_widoku_sam_nie_usuwa_wiersza_z_mat`` (nazwa i
    asercja sprzed fazy 01). Jak wyzej: dla publikacji to faza 02, ten test
    ma zostac xfail do tego czasu.
    """
    # Cale DDL przed INSERT-em (patrz test wyzej). Filtr widoku jest juz
    # aktywny przy tworzeniu rekordu, ale deleted_at jest wtedy NULL, wiec
    # wiersz normalnie wchodzi do bpp_rekord_mat.
    with connection.cursor() as cur:
        _dodaj_deleted_at(cur)
        _filtruj_widok_po_deleted_at(cur)

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
