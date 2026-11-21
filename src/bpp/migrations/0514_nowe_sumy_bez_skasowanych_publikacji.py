"""Ranking autorów przestaje punktować publikacje z kosza.

``bpp_nowe_sumy_<typ>_view`` joinują SUROWE tabele publikacji, więc bez
tego warunku skasowana publikacja dalej wnosi punkty do sum:
``bpp_nowe_sumy_<typ>_view`` -> UNION ALL ``bpp_nowe_sumy_view`` -> modele
``Nowe_Sumy_View``/``Sumy`` (``bpp/models/sumy_views.py``) ->
``ranking_autorow/views.py``.

Wszystkie pięć widoków: dla ciągłych, zwartych i patentów warunek na
tabeli publikacji obejmuje też ich autorstwa (``*_autor`` nie ma własnego
kosza — znika razem z publikacją). Widoki nie mają ``LEFT JOIN``-ów ani
agregatów (sumowanie dzieje się w Django nad ``UNION ALL``), więc zwykły
warunek w ``WHERE`` jest poprawny: skasowana publikacja MA wypaść
z rankingu.

NIEODWRACALNA (brak ``reverse_code``) — jak cały łańcuch soft-delete
``0511``–``0523``; powrót wyłącznie z kopii bazy.
"""

from django.db import connection, migrations

from bpp.migration_util import widok_dopisz_warunek

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


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0513_soft_delete_autorzy_przez_publikacje"),
    ]

    operations = [
        migrations.RunPython(forward),
    ]
