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
3. Repozytoria SIOSTRZANE (to są obiekty bazodanowe, więc konsument nie
   musi mieszkać w repo aplikacji — self-review, 2026-08-07): ``bpp-mcp``
   i ``bpp-skills`` czyste; ``bpp-deploy`` odwołuje się do nich WYŁĄCZNIE
   w komentarzach i w jednej kontrolce diagnostycznej — patrz uwaga niżej.
4. ``flexible_reports``: definicje raportów żyją jako wiersze w bazie
   produkcyjnej, więc z repo nie da się ich sprawdzić. **Potwierdzone przez
   właściciela systemu (2026-08-07): żaden raport nie odpytuje tych
   widoków.** To był jedyny element dowodu oparty na założeniu.

Fazę 01 zweryfikowała tak trzy widoki; faza 02 dołożyła
``bpp_kronika_praca_{doktorska,habilitacyjna}_view``, których żywotności
nikt wcześniej nie sprawdzał — wyszły na jaw, gdy kanarek katalogowy
dostał do zakresu tabele publikacji.

⚠️ DO ZROBIENIA W ``bpp-deploy`` (poza tym repo, nieblokujące):
``scripts/pg-collation-migrate-3-load.sh`` drukuje po załadowaniu bazy
kontrolkę ``SELECT 'kronika views: '||count(*) ... LIKE 'bpp_kronika%'``.
Po tej migracji wypisze ``0`` — a to sanity-check po odtworzeniu bazy, więc
operator ma prawo odczytać zero jako nieudany load. Do zdjęcia razem
z komentarzami w ``lib-pg-collation-migrate.sh`` i
``pg-collation-migrate-2-fix.sh``, które uzasadniają migrację kolacji przez
„5 widoków ``bpp_kronika_*``". Sam ``sed`` celuje we wzorzec ``COLLATE``,
a nie w nazwy widoków, więc skrypty NIE przestają działać.

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
            # Dwie NIEZALEŻNE decyzje w jednej instrukcji:
            #
            # bez CASCADE — gdyby cokolwiek spoza rodziny zdążyło się na
            # którymś oprzeć, chcemy głośnego błędu, a nie cichego zabrania
            # tego czegoś razem z widokiem;
            #
            # z IF EXISTS — bo to piętnastoletnie, martwe widoki i któryś
            # DBA mógł je już ręcznie sprzątnąć; bez tego migracja twardo
            # pada na takiej bazie. IF EXISTS NIE osłabia głośności:
            # przy istniejącej zależności DROP dalej rzuca błąd.
            cur.execute(f"DROP VIEW IF EXISTS {widok}")


def backward(apps, schema_editor):
    load_custom_sql("0499_drop_kronika_views")


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0498_nowe_sumy_bez_skasowanych_publikacji"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
