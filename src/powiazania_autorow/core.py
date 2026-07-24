"""
Core functionality for calculating author connections.
"""

import logging

from django.db import connection, transaction

from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

from .models import AuthorConnection

logger = logging.getLogger(__name__)

# Modele autorstwa, z których liczymy współautorstwa. Każdy ma WŁASNĄ przestrzeń
# rekord_id (Ciągłe/Zwarte/Patenty to osobne tabele), więc liczymy per-tabela i
# sumujemy — rekord_id=5 w jednej tabeli to inna praca niż rekord_id=5 w drugiej.
_MODELE_AUTORSTWA = (
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
    Patent_Autor,
)


def _self_join_sql(db_table):
    """Fragment SELECT: dla jednej tabeli *_Autor liczy, ile WSPÓLNYCH prac
    (DISTINCT rekord_id) dzieli każda nieuporządkowana para autorów.

    Self-join po rekord_id; warunek ``a1.autor_id < a2.autor_id`` daje każdą
    parę dokładnie raz (mniejszy id jako primary) i z definicji wyklucza parę
    autora z samym sobą — nawet gdy autor ma kilka wpisów na tej samej pracy
    (różne typy odpowiedzialności / kolejność). NULL-owe autor_id odpadają przy
    porównaniu ``<``. Join korzysta z istniejącego indeksu unique_together
    ``(rekord, autor, ...)`` — bez potrzeby dodawania nowych indeksów.
    """
    return f"""
        SELECT a1.autor_id AS p,
               a2.autor_id AS s,
               COUNT(DISTINCT a1.rekord_id) AS cnt
          FROM "{db_table}" a1
          JOIN "{db_table}" a2
            ON a1.rekord_id = a2.rekord_id
           AND a1.autor_id < a2.autor_id
         GROUP BY a1.autor_id, a2.autor_id
    """


def calculate_author_connections():
    """Przelicza od zera całą tabelę AuthorConnection z bieżących współautorstw.

    Całość liczona w SQL: self-join per tabela autorstwa (Ciągłe / Zwarte /
    Patenty), zsumowany po parze autorów. Zero round-tripów do Pythona i zero
    materializacji par w pamięci — w odróżnieniu od dawnej wersji, która
    streamowała wszystkie wiersze i budowała ogromny słownik par (O(k^2) na
    publikację, patologia przy pracach z setkami współautorów).

    **Buduj obok, potem podmień.** Wynik self-joinów ląduje najpierw w tabeli
    tymczasowej (``TEMP TABLE``, widocznej tylko dla tej sesji), a dopiero
    gotowy jest przepisywany do tabeli docelowej krótką sekwencją ``DELETE`` +
    ``INSERT ... SELECT`` ze staging-u, owiniętą w ``atomic()``. Dzięki temu
    okno, w którym ``AuthorConnection`` jest zablokowana dla pisarzy (m.in.
    ``update_single_author_connections_task``), skraca się z „czas liczenia +
    czas zapisu" do samego czasu przepisania wierszy. Czytelnicy nie są
    blokowani w żadnym wariancie (MVCC).

    ZASTRZEŻENIE: zysk występuje tylko wtedy, gdy funkcja jest wołana POZA
    zewnętrzną transakcją — czyli na ścieżce produkcyjnej (zadanie Celery,
    komenda zarządzająca). Gdy woła ją coś, co samo trzyma transakcję —
    migracja ``0003_*`` (``RunPython`` jest domyślnie atomic) albo test pod
    ``@pytest.mark.django_db`` — budowanie staging-u dzieje się WEWNĄTRZ tej
    transakcji, ``atomic()`` poniżej degraduje się do savepointu i okno
    blokady jest takie samo jak przed zmianą. Poprawność jest identyczna w
    obu wariantach; różni się wyłącznie długość blokady.

    Semantyka: ``shared_publications_count`` = liczba WSPÓLNYCH publikacji
    (DISTINCT rekord), sumowana po typach prac. Para autorów zapisywana jest raz,
    z mniejszym id jako ``primary_author`` (spójnie z unique_together). Pary
    autora z samym sobą nie powstają.

    Zwraca łączną liczbę utworzonych powiązań.
    """
    table = AuthorConnection._meta.db_table
    union = "\n        UNION ALL\n".join(
        _self_join_sql(m._meta.db_table) for m in _MODELE_AUTORSTWA
    )
    staging = "powiazania_autorow_staging"

    logger.info("Przeliczanie powiązań autorów (SQL)...")
    with connection.cursor() as cur:
        # Faza 1 (długa, bez blokady na tabeli docelowej): policz wszystko do
        # tabeli tymczasowej. TEMP TABLE jest prywatna dla tej sesji i znika
        # przy jej zamknięciu; DROP na starcie zabezpiecza przed resztką po
        # poprzednim przebiegu w tej samej, długo żyjącej sesji workera.
        #
        # Kwalifikacja `pg_temp.` jest istotna: nieskwalifikowana nazwa jest
        # rozwiązywana przez `search_path`, który przy PIERWSZYM przebiegu w
        # sesji (brak jeszcze schematu tymczasowego) celuje w `public` — DROP
        # mierzyłby wtedy w zwykłą tabelę o tej nazwie, nie w nasz staging.
        cur.execute(f'DROP TABLE IF EXISTS pg_temp."{staging}"')
        cur.execute(
            f"""
            CREATE TEMP TABLE "{staging}" AS
            SELECT p AS primary_author_id,
                   s AS secondary_author_id,
                   SUM(cnt) AS shared_publications_count
              FROM (
{union}
              ) sub
             GROUP BY p, s
            """
        )

        try:
            # Faza 2 (krótka, pod blokadą): podmiana zawartości.
            with transaction.atomic():
                # DELETE (nie TRUNCATE): TRUNCATE wywala się błędem ObjectInUse,
                # gdy w tej samej transakcji były wcześniej INSERT-y do tabeli
                # (oczekujące zdarzenia wyzwalaczy FK) — np. w testach owiniętych
                # w transakcję lub gdy recompute leci po innej operacji na tabeli.
                # DELETE bez WHERE to jedno zapytanie, transakcyjne i odporne na
                # ten przypadek. Blok jest atomowy: przy błędzie INSERT-u DELETE
                # też się cofa, więc tabela nigdy nie zostaje pusta.
                cur.execute(f'DELETE FROM "{table}"')
                cur.execute(
                    f"""
                    INSERT INTO "{table}"
                        (primary_author_id, secondary_author_id,
                         shared_publications_count, last_updated)
                    SELECT primary_author_id, secondary_author_id,
                           shared_publications_count, now()
                      FROM pg_temp."{staging}"
                    """
                )
        finally:
            # Staging bywa duży — nie trzymamy go do końca życia sesji workera.
            cur.execute(f'DROP TABLE IF EXISTS pg_temp."{staging}"')

    total = AuthorConnection.objects.count()
    logger.info("Przeliczono %s powiązań autorów.", total)
    return total
