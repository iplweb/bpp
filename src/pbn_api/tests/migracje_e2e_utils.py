"""Wspólne narzędzia testów e2e migracji ``pbn_api``.

Testy puszczają prawdziwy ``MigrationExecutor``, ale cofają i ponownie
stosują WYŁĄCZNIE badane migracje ``pbn_api`` (jawny ``plan``), a nie
„wszystko do migracji X". Cofnięcie ``pbn_api`` do X pociągnęłoby za sobą
wszystkie zależne migracje innych aplikacji — w tym łańcuch soft-delete
``bpp/0510``–``0522``, który jest NIEODWRACALNY (``IrreversibleError``).

Testy MUSZĄ też posprzątać po sobie — inaczej worker testowy zostaje
z niezastosowaną migracją i psuje wszystkie kolejne testy w tym procesie.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def _wykonaj(klucze, wstecz):
    executor = MigrationExecutor(connection)
    graf = executor.loader.graph
    plan = [(graf.nodes[klucz], wstecz) for klucz in klucze]
    # Przy jawnym ``plan`` executor liczy stan projektu z pełnego grafu
    # (``full_plan``), a wykonuje tylko to, co w planie — migracje spoza
    # planu zostają nietknięte.
    executor.migrate(list(klucze), plan=plan)


def cofnij_tylko(*klucze):
    """Cofa DOKŁADNIE podane migracje, w podanej kolejności (od najnowszej).

    Nic poza nimi nie jest cofane — także migracje zależne. Wolno tego
    używać tylko dla migracji, których cofnięcie nie łamie schematu migracji
    późniejszych (np. zdjęcie constraintu, na którym nic nie stoi).
    """
    _wykonaj(klucze, wstecz=True)


def zastosuj_tylko(*klucze):
    """Stosuje DOKŁADNIE podane migracje, w podanej kolejności."""
    _wykonaj(klucze, wstecz=False)


def przywroc_czubek_migracji():
    """Doprowadź bazę workera do NAJNOWSZYCH migracji — WSZYSTKICH aplikacji.

    Stosuje każdą migrację z pełnego grafu, której brakuje w
    ``django_migrations`` — także „dziurę" w środku grafu zostawioną przez
    ``cofnij_tylko``. Samo ``executor.migrate(leaf_nodes())`` by jej NIE
    załatało: liście są zastosowane, więc Django uznałby, że nie ma nic do
    roboty. Idempotentne: na pełnej bazie nic nie robi.
    """
    executor = MigrationExecutor(connection)
    liscie = executor.loader.graph.leaf_nodes()
    zastosowane = executor.loader.applied_migrations
    brakujace = [
        (migracja, False)
        for migracja, _wstecz in executor.migration_plan(liscie, clean_start=True)
        if (migracja.app_label, migracja.name) not in zastosowane
    ]
    if brakujace:
        executor.migrate(liscie, plan=brakujace)
