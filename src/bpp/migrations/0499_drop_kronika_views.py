"""Kasuje MARTWĄ rodzinę siedmiu widoków ``bpp_kronika_*``.

DLACZEGO WSZYSTKIE SIEDEM NARAZ. Faza 01 chciała skasować trzy z nich
(``wydawnictwo_ciagle``/``wydawnictwo_zwarte``/``patent``) i została
zablokowana: zależą od nich dwa widoki nadrzędne, więc goły ``DROP VIEW``
bez ``CASCADE`` nie przechodzi, a ``CASCADE`` po cichu zabrałby też te
nadrzędne. Rozbicie na kilka migracji nic nie daje — graf trzeba rozciąć
w jednym miejscu albo wcale.

DOWÓD MARTWOTY (zweryfikowany 2026-08-07, faza 02):

1. ``pg_depend``: JEDYNE zależności od tych siedmiu widoków są WEWNĄTRZ
   rodziny — ``bpp_kronika_view`` <- ``bpp_kronika_all_unsorted_view`` <-
   pięć widoków liści. Nic spoza rodziny na nich nie stoi. To mocniejszy
   dowód niż grep: obejmuje też widoki i reguły, których nazwa nie zawiera
   słowa „kronika".
2. Kod: zero trafień „kronika" w ``.py``/``.html``/``.json``/``.js``/SQL-u
   poza katalogami migracji i ``baseline-sql/`` (czyli poza definicjami
   samych widoków). Zero ``Meta.db_table`` wskazujących na którykolwiek.

Fazę 01 zweryfikowała tak trzy widoki; faza 02 dołożyła
``bpp_kronika_praca_{doktorska,habilitacyjna}_view``, których żywotności
nikt wcześniej nie sprawdzał — wyszły na jaw, gdy kanarek katalogowy
dostał do zakresu tabele publikacji.

ODWRACALNOŚĆ: ``backward`` odtwarza całą siódemkę z sidecara
``0499_drop_kronika_views.sql``. Plik został WYGENEROWANY z
``pg_get_viewdef()`` na żywym katalogu, a nie przepisany ręcznie — przy
7 KB SQL-a przepisywanie byłoby proszeniem się o cichą literówkę.

⚠️ Po tej migracji trzeba usunąć trzy wpisy ``WYJATKI`` z kanarka
katalogowego (``test_kanarek_katalogowy.py``) — wskazują na widoki, których
już nie ma.
"""

from django.db import connection, migrations

from bpp.migration_util import load_custom_sql

# Kolejnosc KASOWANIA: od szczytu w dol (parasole przed liscmi).
# Odwrotna kolejnosc (odtwarzania) siedzi w sidecarze .sql.
RODZINA_OD_SZCZYTU = [
    "bpp_kronika_view",
    "bpp_kronika_all_unsorted_view",
    "bpp_kronika_wydawnictwo_ciagle_view",
    "bpp_kronika_wydawnictwo_zwarte_view",
    "bpp_kronika_patent_view",
    "bpp_kronika_praca_doktorska_view",
    "bpp_kronika_praca_habilitacyjna_view",
]


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for widok in RODZINA_OD_SZCZYTU:
            # Bez CASCADE ŚWIADOMIE: gdyby cokolwiek spoza rodziny zdążyło
            # się na którymś oprzeć, chcemy głośnego błędu, a nie cichego
            # zabrania tego czegoś razem z widokiem.
            cur.execute(f"DROP VIEW {widok}")


def backward(apps, schema_editor):
    load_custom_sql("0499_drop_kronika_views")


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0498_nowe_sumy_bez_skasowanych_publikacji"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
