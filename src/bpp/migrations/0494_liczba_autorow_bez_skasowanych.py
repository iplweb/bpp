"""``liczba_autorow`` w ``bpp_<typ>_view`` przestaje liczyć soft-deletowane.

Migracja 0489 przefiltrowała widoki ``bpp_*_autorzy`` (te karmią
``bpp_autorzy_mat``), ale ``liczba_autorow`` bierze się z INNEJ rodziny
widoków — ``bpp_wydawnictwo_ciagle_view`` / ``bpp_wydawnictwo_zwarte_view`` /
``bpp_patent_view`` (migracja 0421) — i tam agregat liczył SUROWĄ tabelę
``*_autor``:

    count(bpp_wydawnictwo_ciagle_autor.autor_id) AS liczba_autorow

Skutki zawyżonej ``Rekord.liczba_autorow`` (kolumna ``bpp_rekord_mat``):

- multiseek, kryterium „Ostatnie nazwisko i imię": filtr
  ``kolejnosc ∈ [liczba_autorow-1, liczba_autorow)``
  (``bpp/multiseek_registry/fields/author_fields.py``) celuje w pozycję, na
  której po soft-delete nikogo nie ma — zapytanie CICHO zwraca pustkę;
- sortowanie multiseeka po „liczbie autorów" i samo pole „Liczba autorów".

**Dlaczego ``FILTER``, a nie warunek w ``JOIN``/``WHERE``.** Widok robi
``LEFT JOIN`` do ``*_autor`` i grupuje po id publikacji. Dopisanie
``deleted_at IS NULL`` do ``WHERE`` skasowałoby Z WIDOKU całe publikacje,
którym soft-deletowano WSZYSTKICH autorów (LEFT JOIN + WHERE na kolumnie
prawej strony = INNER JOIN), a więc wywaliłoby je z ``bpp_rekord_mat``
i z całego serwisu. Agregat ``count(...) FILTER (WHERE ...)`` rusza
WYŁĄCZNIE licznik: publikacja bez żywych autorów zostaje w widoku z
``liczba_autorow = 0``, dokładnie jak publikacja, której autorów nigdy nie
było. Poza licznikiem żadna kolumna tych widoków nie sięga do ``*_autor``,
więc to jedyne miejsce wymagające zmiany.

Definicje są GENEROWANE z introspekcji (``pg_get_viewdef``), nie przepisane
do ``.sql`` — patrz docstring 0489. ``CREATE OR REPLACE VIEW`` zachowuje
listę kolumn (``count()`` to ``bigint`` w obu wariantach), więc zależny
``bpp_rekord`` (UNION po pięciu widokach) nie jest kasowany.

UWAGA (eventual consistency, NIE regresja tej migracji): trigger na tabeli
``*_autor`` odświeża tylko ``bpp_autorzy_mat``. ``liczba_autorow`` w
``bpp_rekord_mat`` przelicza się dopiero, gdy flush denorm dotknie wiersza
publikacji (opis bibliograficzny zależy od autorów) — tak samo po TWARDYM
kasowaniu autorstwa. Patrz komentarz przy polu ``Rekord.liczba_autorow``.
"""

import importlib

from django.db import connection, migrations

from bpp.migration_util import viewdef

_p0433 = importlib.import_module("bpp.migrations.0433_cache_trigger_when_gate")

# (widok bpp_<typ>_view, tabela through *_autor, którą liczy)
LICZNIKI = [
    ("bpp_wydawnictwo_ciagle_view", "bpp_wydawnictwo_ciagle_autor"),
    ("bpp_wydawnictwo_zwarte_view", "bpp_wydawnictwo_zwarte_autor"),
    ("bpp_patent_view", "bpp_patent_autor"),
]

# Tabele publikacji, których bramkę WHEN regenerujemy po zmianie widoku.
TABELE_PUBLIKACJI = {"bpp_wydawnictwo_ciagle", "bpp_wydawnictwo_zwarte", "bpp_patent"}


def _bez_filtra(tabela):
    return f"count({tabela}.autor_id) AS liczba_autorow"


def _z_filtrem(tabela):
    return (
        f"count({tabela}.autor_id) FILTER "
        f"(WHERE {tabela}.deleted_at IS NULL) AS liczba_autorow"
    )


def _przepisz_agregat(cur, widok, stary, nowy):
    """``CREATE OR REPLACE VIEW`` z podmienionym JEDNYM wystąpieniem agregatu.

    ``!= 1`` (a nie ``== 0``) jest celowe: gdyby przyszła zmiana dołożyła drugi
    ``count(...)`` po tej samej tabeli, ślepy ``replace`` podmieniłby oba.
    Głośny błąd migracji jest lepszy niż cicha zmiana semantyki widoku.
    """
    definicja = viewdef(cur, widok)
    if definicja.count(nowy) == 1 and stary not in definicja:
        return  # już przepisane (idempotencja)
    ile = definicja.count(stary)
    if ile != 1:
        raise RuntimeError(
            f"{widok}: oczekiwano DOKLADNIE jednego wystapienia {stary!r}, "
            f"znaleziono {ile} -- nie podmieniam na slepo."
        )
    cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {definicja.replace(stary, nowy)}")


def _regeneruj_bramke():
    """Bramka WHEN triggerów UPDATE tabel PUBLIKACJI (logika ``0433.forward``).

    Bramka jest wyliczana z ``pg_depend`` PO definicji widoku, więc każda
    zmiana definicji musi być domknięta jej regeneracją — inaczej wraca błąd,
    który ta faza już raz naprawiała (0489, krok 3).

    Tu regeneracja jest z konstrukcji NO-OPEM: ``_gate_columns`` pyta o
    kolumny TABELI PUBLIKACJI referowane przez widok, a ``FILTER (WHERE
    *_autor.deleted_at ...)`` dokłada zależność od kolumny tabeli THROUGH.
    Zostawiamy ją mimo to — jako niezmiennik „ruszyłeś widok, przelicz
    bramkę", którego nie chcemy uzależniać od tego, czy akurat dziś wychodzi
    ta sama lista kolumn.
    """
    with connection.cursor() as cur:
        for tabela, refresh_fn, widoki in _p0433.GATED:
            if tabela not in TABELE_PUBLIKACJI:
                continue
            kolumny = _p0433._gate_columns(cur, tabela, widoki)
            if not kolumny:
                # Bezpiecznik z 0433: bez kolumn powstałby niebramkowany
                # UPDATE (trigger na każdą zmianę wiersza publikacji).
                raise RuntimeError(
                    f"bramka dla {tabela}: pg_depend nie zwrocil zadnej kolumny "
                    f"(widoki={widoki}) -- nie tworze niezbramkowanego UPDATE"
                )
            when = _p0433._when_clause(kolumny)
            cur.execute(f"DROP TRIGGER IF EXISTS {tabela}_cache_upd ON {tabela};")
            cur.execute(
                f"CREATE TRIGGER {tabela}_cache_upd AFTER UPDATE ON {tabela} "
                f"FOR EACH ROW WHEN ({when}) "
                f"EXECUTE PROCEDURE {refresh_fn}();"
            )


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for widok, tabela in LICZNIKI:
            _przepisz_agregat(cur, widok, _bez_filtra(tabela), _z_filtrem(tabela))
    _regeneruj_bramke()


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        for widok, tabela in LICZNIKI:
            _przepisz_agregat(cur, widok, _z_filtrem(tabela), _bez_filtra(tabela))
    _regeneruj_bramke()


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0493_autor_zdjecie_starych_unique"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
