"""Ranking autorów przestaje punktować soft-deletowane autorstwa.

``bpp_nowe_sumy_*_view`` (migracja 0458) joinują SUROWE tabele ``*_autor``,
więc po soft-delete autorstwo dalej wnosi punkty do sum. Ścieżka:
``bpp_nowe_sumy_{patent,wydawnictwo_ciagle,wydawnictwo_zwarte}_view``
-> UNION ALL ``bpp_nowe_sumy_view`` -> modele ``Nowe_Sumy_View``/``Sumy``
(``bpp/models/sumy_views.py``) -> ``ranking_autorow/views.py``.

Najgorszy scenariusz: deduplikator autorów przenosi autorstwa do autora
docelowego i kasuje źródłowe — od fazy 01 MIĘKKO. Bez tego filtra duplikat
zostaje w rankingu z pełną punktacją bezterminowo (a praca jest liczona
podwójnie: raz na autorze docelowym, raz na skasowanym duplikacie).

Dwa pozostałe widoki unii — ``bpp_nowe_sumy_praca_doktorska_view`` i
``..._praca_habilitacyjna_view`` — NIE mają tabeli through (autor leży na
wierszu publikacji) i faza 01 nie robi ich soft-delete; zostają bez zmian.
"""

from django.db import connection, migrations

from bpp.migration_util import widok_dopisz_warunek, widok_usun_warunek

# (widok sum, tabela through *_autor, którą joinuje)
SUMY = [
    ("bpp_nowe_sumy_wydawnictwo_ciagle_view", "bpp_wydawnictwo_ciagle_autor"),
    ("bpp_nowe_sumy_wydawnictwo_zwarte_view", "bpp_wydawnictwo_zwarte_autor"),
    ("bpp_nowe_sumy_patent_view", "bpp_patent_autor"),
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
        ("bpp", "0494_liczba_autorow_bez_skasowanych"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
