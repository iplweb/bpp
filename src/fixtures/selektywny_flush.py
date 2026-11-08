"""Selektywne sprzątanie bazy po teście transakcyjnym (zamiast pełnego flush-a).

Po każdym teście transakcyjnym Django robi ``flush``: ``TRUNCATE`` wszystkich
(~260) tabel modeli ``CASCADE`` + ``post_migrate`` (seedy: content types,
uprawnienia, grupy, site). Zmierzone: ~0,25 s TRUNCATE + ~0,2-0,4 s
``post_migrate`` na KAŻDY test transakcyjny — niezależnie od tego, czy test
dotknął dwóch tabel, czy żadnej.

Stan bazy po pełnym flush-u (nazywany tu **S0**) jest deterministyczny: puste
wszystkie tabele objęte flush-em (zbiór **C** = tabele modeli + domknięcie
``CASCADE`` po FK, w tym niezarządzane ``bpp_rekord_mat``/``bpp_autorzy_mat``),
poza kilkoma, które zasiewa ``post_migrate`` (``django_content_type``,
``auth_permission``, ``auth_group``, ``auth_group_permissions``,
``django_site``). Mechanizm:

1. Pierwszy teardown w procesie robi PEŁNY flush i zapamiętuje S0: listę C,
   OID-y tabel, które tabele są w S0 niepuste, i ich odcisk
   (``count(*)`` + suma ``hashtextextended`` z tekstu wiersza).
2. Kolejne teardowny jednym zapytaniem sprawdzają TREŚĆ (nie statystyki):
   tabele puste w S0 → ``EXISTS``; tabele niepuste w S0 → odcisk. Patrzymy na
   dane scommitowane przez KOGOKOLWIEK (wątek live servera, Celery eager,
   commit z innego połączenia) — statystyki ``pg_stat_*`` odpadły, bo inne
   backendy wypychają je z opóźnieniem (``PGSTAT_MIN_INTERVAL``) i nie da się
   ich wymusić z zewnątrz.
3. Brudne tabele (puste w S0, a teraz z wierszami) czyścimy ``DELETE`` pod
   ``session_replication_role = replica`` (bez triggerów denorm/mat i bez
   sprawdzania FK — wszystkie niepuste tabele C są w zbiorze i tak, więc
   żaden FK nie zostaje wiszący). ``DELETE`` zamiast ``TRUNCATE``: TRUNCATE
   brudnych tabel wymaga ``CASCADE``, które wciąga dziesiątki tabel
   referujących ``bpp_autor``/``bpp_wydawnictwo_*`` → zmierzone ~170 ms
   wobec ~2 ms dla DELETE.
4. Tabele zasiewane, które test zmienił (najczęściej ``django_site`` —
   fikstury multisite), dostają z powrotem dokładnie wiersze z S0 (kopia
   zrobiona przy budowie S0: ``DELETE`` + ``INSERT`` z ``array_agg(x::text)``),
   plus czyszczenie cache ``ContentType``/``Site``.
5. ``post_migrate`` NIE jest wołany: tabele zasiewane mają treść S0, więc
   wynik jest dokładnie S0. Zresztą ``post_migrate`` NIE jest idempotentny —
   drugie wywołanie na S0 podnosi ``auth_group_permissions`` z 316 do 432
   wierszy (``odtworz_grupy`` leci przed ``create_permissions`` części
   aplikacji) — więc „DELETE + post_migrate" dałoby INNY stan niż pełny
   flush.

Różnica wobec pełnego flush-a: pełny flush nadaje zasiewanym wierszom NOWE
id (``reset_sequences=False``), tu zostają te same. Sekwencje — bez zmian
w obu wariantach.

Fallback do pełnego flush-a (i przebudowa S0), gdy:

- inny backend tej bazy ma otwartą transakcję (pełny TRUNCATE poczekałby na
  jej koniec i wymiótł jej dane; DELETE by ich nie zobaczył),
- zmieniły się OID-y tabel (test przebudował schemat),
- po sprzątaniu coś nadal różni się od S0 (współbieżny zapis),
- dowolny błąd bazy.

Przełączniki (zmienne środowiskowe):

- ``BPP_FLUSH_PELNY=1`` — wyłącza mechanizm (zawsze pełny flush jak dawniej).
- ``BPP_FLUSH_WERYFIKUJ=1`` — tryb kontrolny: po selektywnym sprzątaniu
  sprawdza, że wszystkie tabele C mają DOKŁADNIE odcisk S0, następnie robi
  pełny flush i porównuje odciski semantyczne (liczba wierszy + hash bez
  kolumn ``id``/``*_id``, bo flush bez ``reset_sequences`` przenumerowuje
  zasiewane wiersze) WSZYSTKICH tabel w ``public``. Rozjazd → wyjątek.
- ``BPP_FLUSH_STATYSTYKI=<katalog>`` — każdy teardown dopisuje linię JSON
  (test, wynik, powód, czas) do ``<katalog>/<worker>.jsonl``.
"""

import json
import logging
import os
import time

logger = logging.getLogger(__name__)


class PotrzebnyPelnyFlush(Exception):
    """Selektywne sprzątanie nie gwarantuje stanu S0 — trzeba pełnego flush-a."""


class RozjazdWeryfikacji(Exception):
    """Tryb ``BPP_FLUSH_WERYFIKUJ``: stan po selektywnym sprzątaniu ≠ flush."""


# alias bazy -> _StanS0
_STAN = {}


def wlaczony():
    return not os.environ.get("BPP_FLUSH_PELNY")


def weryfikacja():
    return bool(os.environ.get("BPP_FLUSH_WERYFIKUJ"))


def zapomnij(db_name):
    _STAN.pop(db_name, None)


def _q(connection, nazwa):
    return connection.ops.quote_name(nazwa)


def _odcisk_sql(connection, tabela, semantyczny=False):
    """Wyrażenie SQL zwracające tekstowy odcisk zawartości tabeli."""
    t = _q(connection, tabela)
    if semantyczny:
        # Bez kolumn kluczy: flush bez reset_sequences nadaje zasiewanym
        # wierszom nowe id, a FK do nich też się zmieniają.
        wiersz = (
            "(SELECT jsonb_object_agg(k, v) FROM jsonb_each(to_jsonb(x)) AS e(k, v)"
            " WHERE k <> 'id' AND k NOT LIKE '%\\_id')::text"
        )
    else:
        wiersz = "x::text"
    return (
        f"(SELECT count(*)::text || ':' || "
        f"coalesce(sum(hashtextextended(coalesce({wiersz}, ''), 0)), 0)::text "
        f"FROM {t} AS x)"
    )


class _StanS0:
    def __init__(self, connection):
        self.nazwa_bazy = connection.settings_dict["NAME"]
        with connection.cursor() as cur:
            cur.execute(
                "SELECT c.relname, c.oid FROM pg_class c "
                "WHERE c.relnamespace = 'public'::regnamespace "
                "AND c.relkind IN ('r', 'p')"
            )
            oidy_wszystkich = dict(cur.fetchall())

            # Odwrotny graf: tabela -> tabele, które TRUNCATE ... CASCADE
            # tej tabeli też wyczyści (FK do niej + dzieci dziedziczenia).
            cur.execute(
                "SELECT confrelid::regclass::text, conrelid::regclass::text "
                "FROM pg_constraint WHERE contype = 'f' "
                "UNION "
                "SELECT inhparent::regclass::text, inhrelid::regclass::text "
                "FROM pg_inherits"
            )
            self.kaskada = {}
            for cel, zrodlo in cur.fetchall():
                cel, zrodlo = cel.strip('"'), zrodlo.strip('"')
                self.kaskada.setdefault(cel, set()).add(zrodlo)

        zarzadzane = connection.introspection.django_table_names(
            only_existing=True, include_views=False
        )
        self.kandydaci = sorted(self.domkniecie(zarzadzane) & set(oidy_wszystkich))
        self.oidy = [oidy_wszystkich[t] for t in self.kandydaci]

        with connection.cursor() as cur:
            cur.execute(
                "SELECT "
                + ", ".join(
                    f"EXISTS(SELECT 1 FROM {_q(connection, t)})" for t in self.kandydaci
                )
            )
            niepuste = [
                t
                for t, jest in zip(self.kandydaci, cur.fetchone(), strict=True)
                if jest
            ]
        self.niepuste_s0 = niepuste
        self.puste_s0 = [t for t in self.kandydaci if t not in set(niepuste)]
        self.zapytanie = (
            "SELECT ARRAY["
            + ", ".join(
                f"EXISTS(SELECT 1 FROM {_q(connection, t)})" for t in self.puste_s0
            )
            + "]::boolean[], ARRAY["
            + ", ".join(_odcisk_sql(connection, t) for t in self.niepuste_s0)
            + "]::text[]"
        )
        with connection.cursor() as cur:
            cur.execute(self.zapytanie)
            _, odciski = cur.fetchone()
        self.odciski_s0 = dict(zip(self.niepuste_s0, odciski, strict=True))
        # Kopia wierszy tabel zasiewanych (kilka tabel, ~1,7 tys. wierszy) —
        # test, który je zmieni (np. ``Site``), dostaje je przywrócone 1:1
        # zamiast pełnego flush-a.
        self.kopie_s0 = {}
        with connection.cursor() as cur:
            for t in self.niepuste_s0:
                cur.execute(
                    f"SELECT coalesce(array_agg(x::text), '{{}}') "
                    f"FROM {_q(connection, t)} AS x"
                )
                self.kopie_s0[t] = cur.fetchone()[0]
        self.przygotowane_dla = None

        if weryfikacja():
            self.odcisk_dokladny_s0 = odcisk_wszystkich(connection, self.kandydaci)

    def domkniecie(self, tabele):
        wynik = set(tabele)
        stos = list(tabele)
        while stos:
            for zalezna in self.kaskada.get(stos.pop(), ()):
                if zalezna not in wynik:
                    wynik.add(zalezna)
                    stos.append(zalezna)
        return wynik

    def wykonaj_zapytanie(self, connection):
        """Zapytanie o brud jako PREPARE/EXECUTE (planowanie ~260 podzapytań
        kosztuje ~12 ms; EXECUTE przygotowanego ~1 ms)."""
        with connection.cursor() as cur:
            surowe = connection.connection
            if self.przygotowane_dla is not surowe:
                # NIE ``DEALLOCATE ALL`` — psycopg sam przygotowuje zapytania
                # po stronie serwera i zgubiłby swoje.
                cur.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_prepared_statements "
                    "WHERE name = 'bpp_flush_brud')"
                )
                if cur.fetchone()[0]:
                    cur.execute("DEALLOCATE bpp_flush_brud")
                cur.execute("PREPARE bpp_flush_brud AS " + self.zapytanie)
                self.przygotowane_dla = surowe
            cur.execute("EXECUTE bpp_flush_brud")
            return cur.fetchone()

    def brudne(self, connection):
        puste_teraz, odciski = self.wykonaj_zapytanie(connection)
        brudne = [t for t, jest in zip(self.puste_s0, puste_teraz, strict=True) if jest]
        zmienione_s0 = [
            t
            for t, odc in zip(self.niepuste_s0, odciski, strict=True)
            if odc != self.odciski_s0[t]
        ]
        return brudne, zmienione_s0


def odcisk_wszystkich(connection, tabele, semantyczny=False):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT ARRAY["
            + ", ".join(_odcisk_sql(connection, t, semantyczny) for t in tabele)
            + "]::text[]"
        )
        return dict(zip(tabele, cur.fetchone()[0], strict=True))


def tabele_public(connection):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT relname FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p') "
            "ORDER BY relname"
        )
        return [r[0] for r in cur.fetchall()]


def zbuduj_stan(db_name):
    """Wołać ZARAZ po pełnym flush-u (+ post_migrate) — zapamiętuje S0."""
    from django.db import connections

    _STAN[db_name] = _StanS0(connections[db_name])


def _sprawdz_inne_transakcje(cur):
    cur.execute(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND pid <> pg_backend_pid() "
        "AND backend_type = 'client backend' AND xact_start IS NOT NULL"
    )
    if cur.fetchone()[0]:
        raise PotrzebnyPelnyFlush("otwarta transakcja innego backendu")


def sprzataj(db_name):
    """Przywraca S0 bez pełnego flush-a. Zwraca liczbę wyczyszczonych tabel.

    Rzuca ``PotrzebnyPelnyFlush``, gdy nie da się zagwarantować S0.
    """
    from django.db import connections, transaction

    connection = connections[db_name]
    stan = _STAN.get(db_name)
    if stan is None:
        raise PotrzebnyPelnyFlush("brak S0 (pierwszy teardown)")
    if stan.nazwa_bazy != connection.settings_dict["NAME"]:
        raise PotrzebnyPelnyFlush("inna baza niż przy S0")
    if connection.in_atomic_block:
        raise PotrzebnyPelnyFlush("teardown wewnątrz transakcji")

    with connection.cursor() as cur:
        _sprawdz_inne_transakcje(cur)
        cur.execute(
            "SELECT count(*) FROM pg_class WHERE oid = ANY(%s::oid[])", [stan.oidy]
        )
        if cur.fetchone()[0] != len(stan.oidy):
            raise PotrzebnyPelnyFlush("zmienione OID-y tabel")

    brudne, zmienione_s0 = stan.brudne(connection)
    if not brudne and not zmienione_s0:
        return 0

    # Pod ``replica`` nie odpalają triggery (denorm, *_mat) ani kontrole FK.
    # Spójność FK i tak jest zachowana: po wszystkim tabele C spoza S0 są
    # puste, a tabele zasiewane mają dokładnie wiersze z S0 (które w S0
    # wskazywały wyłącznie na siebie nawzajem).
    with transaction.atomic(using=db_name):
        with connection.cursor() as cur:
            cur.execute("SET LOCAL session_replication_role = replica")
            if brudne:
                cur.execute(
                    "; ".join(f"DELETE FROM {_q(connection, t)}" for t in brudne)
                )
            for t in zmienione_s0:
                q = _q(connection, t)
                cur.execute(f"DELETE FROM {q}")
                cur.execute(
                    f"INSERT INTO {q} OVERRIDING SYSTEM VALUE "
                    f"SELECT (v::{q}).* FROM unnest(%s::text[]) AS v",
                    [stan.kopie_s0[t]],
                )
    if zmienione_s0:
        _wyczysc_cache_zasiewanych(zmienione_s0)

    brudne_po, zmienione_po = stan.brudne(connection)
    if brudne_po or zmienione_po:
        raise PotrzebnyPelnyFlush(f"po DELETE nadal brudne: {brudne_po + zmienione_po}")
    return len(brudne) + len(zmienione_s0)


def _wyczysc_cache_zasiewanych(tabele):
    """Cache procesu trzymające wiersze tabel zasiewanych — po przywróceniu
    S0 mogą wskazywać na wiersze, które test dodał, a my usunęliśmy."""
    if "django_content_type" in tabele:
        from django.contrib.contenttypes.models import ContentType

        ContentType.objects.clear_cache()
    if "django_site" in tabele:
        from django.contrib.sites.models import SITE_CACHE

        SITE_CACHE.clear()


def zweryfikuj_przed_flushem(db_name):
    """Tryb kontrolny, krok 1: stan po sprzątaniu == S0 co do bajtu."""
    from django.db import connections

    connection = connections[db_name]
    stan = _STAN[db_name]
    teraz = odcisk_wszystkich(connection, stan.kandydaci)
    rozjazd = {
        t: (stan.odcisk_dokladny_s0[t], teraz[t])
        for t in stan.kandydaci
        if teraz[t] != stan.odcisk_dokladny_s0[t]
    }
    if rozjazd:
        raise RozjazdWeryfikacji(f"stan po sprzątaniu ≠ S0: {rozjazd}")
    tabele = tabele_public(connection)
    return tabele, odcisk_wszystkich(connection, tabele, semantyczny=True)


def zweryfikuj_po_flushu(db_name, tabele, przed):
    """Tryb kontrolny, krok 2: pełny flush dałby to samo (semantycznie)."""
    from django.db import connections

    connection = connections[db_name]
    if tabele_public(connection) != tabele:
        raise RozjazdWeryfikacji("lista tabel zmieniła się podczas flush-a")
    po = odcisk_wszystkich(connection, tabele, semantyczny=True)
    rozjazd = {t: (przed[t], po[t]) for t in tabele if przed[t] != po[t]}
    if rozjazd:
        raise RozjazdWeryfikacji(f"selektywnie ≠ pełny flush: {rozjazd}")


def zapisz_statystyke(wynik, powod, czas):
    katalog = os.environ.get("BPP_FLUSH_STATYSTYKI")
    if not katalog:
        return
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    linia = {
        "test": os.environ.get("PYTEST_CURRENT_TEST", "?"),
        "wynik": wynik,
        "powod": powod,
        "czas": round(czas, 5),
    }
    try:
        os.makedirs(katalog, exist_ok=True)
        with open(os.path.join(katalog, f"{worker}.jsonl"), "a") as f:
            f.write(json.dumps(linia, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("Nie udało się zapisać statystyki flush-a")


def zmierz():
    return time.perf_counter()
