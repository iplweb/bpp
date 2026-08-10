"""Wspólne narzędzia testów e2e migracji ``pbn_api``.

Testy, które puszczają prawdziwy ``MigrationExecutor`` w tył i w przód,
MUSZĄ posprzątać po sobie — inaczej worker testowy zostaje na starej
migracji i psuje wszystkie kolejne testy w tym procesie.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def przywroc_czubek_migracji_pbn_api():
    """Doprowadź bazę workera do NAJNOWSZEJ migracji ``pbn_api``.

    ⚠️ Celowo ``leaf_nodes()``, a NIE zaszyty numer migracji. Cofnięcie się
    do stanu „PRZED" odapplikowuje WSZYSTKO powyżej, więc powrót do stałej
    zostawia bazę o tyle migracji w tyle, ile ich od tamtej pory przybyło —
    a kolejny test, który dotknie nowej kolumny, wywala się
    ``UndefinedColumn`` w miejscu bez żadnego związku z przyczyną.

    Tak właśnie było: jeden test e2e wracał na ``0077``, drugi na ``0079``,
    więc dodanie ``0080`` (``SentData.withdrawn_at``, faza 05 soft-delete)
    wywróciło Playwrightowy test admina ``SentData``. Zaszyty numer jest
    prawdziwy wyłącznie do najbliższej migracji w tej aplikacji; czubek
    grafu jest prawdziwy zawsze.
    """
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes("pbn_api"))
