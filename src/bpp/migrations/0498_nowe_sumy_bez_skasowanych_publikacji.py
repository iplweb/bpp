"""Ranking autorów przestaje punktować soft-deletowane PUBLIKACJE.

Dopełnienie migracji ``0495``, która zamknęła w tych widokach wymiar
AUTORSTWA (``*_autor.deleted_at``). Wymiar PUBLIKACJI został wtedy otwarty,
bo publikacje stały się soft-delete dopiero w fazie 02 (``0496``).

Bez tego filtra soft-deletowana publikacja dalej wnosi punkty do sum:
``bpp_nowe_sumy_<typ>_view`` -> UNION ALL ``bpp_nowe_sumy_view`` -> modele
``Nowe_Sumy_View``/``Sumy`` (``bpp/models/sumy_views.py``) ->
``ranking_autorow/views.py``.

Zakres jest SZERSZY niż w ``0495``: tamta objęła 3 widoki (tylko typy
z through-modelem), ta obejmuje wszystkie 5. ``praca_doktorska`` i
``praca_habilitacyjna`` nie mają tabeli ``*_autor`` — autor leży na wierszu
publikacji — więc ``0495`` nie miała tam czego filtrować, ale soft-delete
samej pracy dotyczy ich tak samo jak reszty.

Widoki ustalone INWENTARYZACJĄ kanarka katalogowego na starcie fazy 02
(``docs/superpowers/reviews/2026-08-07-faza-02-inwentaryzacja-widokow.md``),
nie zgadywaniem — plan fazy 02 miał dla nich wyłącznie ostrzeżenie
„sprawdź, czy wymagają poprawki". Wymagają, wszystkie pięć.

PUŁAPKA AGREGATU TU NIE WYSTĘPUJE (sprawdzone, nie założone). Handoff (§3.2)
ostrzega, że warunek w ``WHERE`` degeneruje ``LEFT JOIN`` do ``INNER JOIN``,
przez co wiersz z zerem znika zamiast wyzerować licznik. Te widoki:

- nie mają ANI JEDNEGO ``LEFT JOIN``-a (złączenia po przecinku albo jawne
  ``JOIN``, czyli semantyka wewnętrzna od początku),
- nie mają ``GROUP BY`` ani żadnej funkcji agregującej — sumowanie dzieje
  się dopiero w modelach Django, nad ``UNION ALL``.

Semantyka jest tu zresztą odwrotna niż przy ``liczba_autorow``: skasowana
publikacja MA wypaść z rankingu, a nie zostać w nim z zerem. Zwykły warunek
w ``WHERE`` jest więc poprawną konstrukcją, a nie skrótem.
"""

from django.db import connection, migrations

from bpp.migration_util import widok_dopisz_warunek, widok_usun_warunek

# (widok sum, tabela PUBLIKACJI, którą joinuje)
SUMY = [
    ("bpp_nowe_sumy_wydawnictwo_ciagle_view", "bpp_wydawnictwo_ciagle"),
    ("bpp_nowe_sumy_wydawnictwo_zwarte_view", "bpp_wydawnictwo_zwarte"),
    ("bpp_nowe_sumy_patent_view", "bpp_patent"),
    ("bpp_nowe_sumy_praca_doktorska_view", "bpp_praca_doktorska"),
    ("bpp_nowe_sumy_praca_habilitacyjna_view", "bpp_praca_habilitacyjna"),
]


def _warunek(tabela):
    return f"{tabela}.deleted_at IS NULL"


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for widok, tabela in SUMY:
            widok_dopisz_warunek(cur, widok, _warunek(tabela))


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        for widok, tabela in SUMY:
            widok_usun_warunek(cur, widok, _warunek(tabela))


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0497_soft_delete_rekord_views"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
